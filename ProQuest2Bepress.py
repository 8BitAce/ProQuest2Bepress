import ConfigParser
import lxml.etree as ET
import os
import re
import smtplib
import subprocess
import sys
import textwrap
import time
import zipfile

from email import encoders
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

config = None
SLEEP_TIME = None
UPLOAD_DIR = None
DB_DIR = None
XSLT_PATH = None
RESULT_EMAIL = None
SMTP_SERVER = None
SMTP_USER = None
SMTP_PASSWORD = None
DBUPLOADER_PATH = None

# Pattern for shared links returned by dropbox_uploader.sh
# Captures the URL
share_link_pattern = re.compile(r' > Share link: (.*)\n')
# Pattern for fulltext links in transformed xml
# Captures the URL
fulltext_pattern = re.compile(r'<fulltext-url>(.*)</fulltext-url>')
# Pattern for xml header (e.g. <?xml version="1.0" encoding="UTF-8"?>)
xml_header_pattern = re.compile(r'<\?xml(.+?)\?>')
# Pattern for attachments
attachment_pattern = re.compile(r'<DISS_file_name>(.*)</DISS_file_name>')

class MyException(Exception):
    pass


def listdir_fullpath(d):
    """
    Returns directory listing with FULL paths.
    Parameters:
        d: The directory to list.
    """
    return [os.path.join(d, f) for f in os.listdir(d)]


def add_slash(m):
    """
    Helper function that appends a / if one does not exist.
    Prameters:
        m: The string to append to.
    """
    if m[-1] != "/":
        return m + "/"
    else:
        return m


def unzip(folder, path):
    """
    Parameters:
        folder: Path to specific upload folder
        path: Full path to .zip file
    Returns:
        (String) Path to unzipped directory.
    """
    filename = os.path.basename(os.path.normpath(path))
    working_dir = os.path.join(folder, os.path.splitext(filename)[0])
    try:
        os.mkdir(working_dir)
    except OSError as e:
        print path + ": " + "That directory already exists! Possible unclean runthrough?"
        print "Sending error report..."
        error_msg = "Tried to extract %s but %s already exists! This means that the script has already tried processing "\
                    "this file. The script has likely forgotten what files it has seen (check  that .seen.txt and .broken.txt exist)"\
                    % (filename, working_dir)
        email_failure(filename, error_msg)
        raise MyException("Unclean runthrough")

    try:
        with zipfile.ZipFile(path, 'r') as myzip:
            myzip.extractall(working_dir)
        return add_slash(working_dir)
    except IOError as e:
        print path + ": " + "No such file in upload directory!"
        print "Sending error report..."
        os.rmdir(working_dir)
        email_failure(filename, "Tried to extract %s but there was no such file in %s!" % (filename, folder))
        raise MyException("File missing")


def transform_files(file_dir):
    """
    Transforms an unzipped ProQuest etd directory by:
        1) Combining all xml data
        2) Transforming combined data using XSLT
        3) Uploading resource files to Dropbox and inserting links into the xml.
    Parameters:
        file_dir: The full path to the unzipped ProQuest etd directory.
    """
    xmls = []
    resource_files = []
    for dirpath, _, files in os.walk(file_dir):
        for filen in files:
            filepath = os.path.join(dirpath, filen)
            if os.path.splitext(filepath)[1] != ".xml":
                resource_files += [filepath]
            else:
                xmls += [filepath]

    if len(xmls) > 1:
        print "More than one xml file"

    dirname = file_dir.split("/")[-2]
    working_dir = file_dir

    print "Combining XMLs..."
    combine_xmls(file_dir, xmls)

    print "Transforming using XSLT..."
    dom = ET.parse(working_dir + "Combined.xml")
    xslt = ET.parse(XSLT_PATH)
    transform = ET.XSLT(xslt)
    newdom = transform(dom)
    result = ET.tostring(newdom, pretty_print=True)
    with open(working_dir + "Transformed.xml", "wb") as f:
        f.write(result)

    print "Uploading files and inserting links..."
    dropboxify(file_dir, working_dir + "Transformed.xml", resource_files)

    if len(resource_files) <= 1:
        email_success(dirname)
    else:
        attachments = []
        for xml in xmls:
            with open(xml) as f:
                xml_text = f.read()
                atts = re.findall(attachment_pattern, xml_text)
                if len(atts) > 0:
                    attachments += re.findall(attachment_pattern, xml_text)
        email_success_attachments(dirname, attachments)
    

def combine_xmls(dirpath, xmls):
    """
    Creates a ombined xml document by:
        1) Writing the necessary xml headers and root tags
        2) Stripping the header from all input documnets
        3) Concatenating the resulting files
    Parameters:
        dirpath: Full path to unzipped etd directory
        xmls: List containing full paths to each xml file
    Side-Effects:
        Writes combined xmls to Combined.xml
    """
    dirname = os.path.basename(os.path.normpath(dirpath))
    with open(dirpath + "/Combined.xml", "ab+") as f:
        f.write("""<?xml version="1.0" encoding="UTF-8"?>\r\n""")
        f.write("""<?xml-stylesheet type="text/xsl" href="result.xsl"?>\r\n""")
        f.write("""<DISS_Documents>""")
        for xml in xmls:
            with open(xml, "rb") as xmlf:
                xml_text = xmlf.read()
                stripped_xml_text = re.sub(xml_header_pattern, "", xml_text)
                f.write(stripped_xml_text)
        f.write("""</DISS_Documents>""")


#A mapping of resource document names to Dropbox URLs
link_map = dict()

def replace_link(m):
    """
    Takes a <fulltext-url> tag and replaces the relative URL with the appropriate Dropbox link.
    Parameters:
        m: The sting containing the full tag.
    """
    inner_link = m.group(1)
    try:
        new_link = link_map[inner_link]
    except Exception as e:
        print "Unmatched file!"
        print "Sending error report..."
        error_msg = "A file referenced in the xml could not be mapped to a Dropbox url.\n"\
                    "Full error:\n"\
                    "%s" % (e)
        raise MyException("Unmatched file")

    return "<fulltext-url>" + new_link + "</fulltext-url>"


def dropboxify(dirpath, xml, resource_files):
    """
    Converts a combined xml document into one ready for Bepress uploading by:
        1) Uploading resources to dropbox
        2) Generating Dropbox share links
        3) Inserting links into the xml
    Parameters:
        dirpath: Full path to unzipped ProQuest ETD directory
        xml: Path to the combined xml file
        resource_files: A list containing full paths to all resource files (.pdf, etc.)
    Side-Effects:
        Writes completed xml to Output.xml
    """
    global link_map
    link_map = dict()

    # Base name of unzipped ETD directory
    dirname = os.path.basename(os.path.normpath(dirpath))

    # Upload all the resource files to dropbox and generate links for each
    # The resulting generated links get added to the link_map
    for fpath in resource_files:
        upload_folder = dirpath.split("/")[-3]
        fname = os.path.basename(fpath)
        try:
            subprocess.check_call([DBUPLOADER_PATH, "upload", fpath, DB_DIR + "/" + upload_folder + "/" + dirname + "/" + fname])
            output = subprocess.check_output([DBUPLOADER_PATH, "share", DB_DIR + "/" + upload_folder + "/" + dirname + "/" + fname])
            match = re.search(share_link_pattern, output)
            if match != None:
                share_link = match.group(1)
                share_link = share_link[:-1] + "1"
                #print fname + ": " + share_link
                link_map[fname] = share_link
        except Exception as e:
            print e
            print "Error uploading to dropbox!"
            print "Sending error report..."
            error_msg = "There was a problem uploading %s to Dropbox.\n"\
                        "Full error follows:\n"\
                        "%s" % (fname, e)
            email_failure(dirname + ".zip", error_msg)
            raise MyException("Dropbox upload error")

    # Where we want to put the resulting files
    working_dir = dirpath
    # Base name of original xml
    xml_basename = os.path.basename(xml)
    # Name of our finished xml file
    finished_fname = dirname + "_Output.xml"

    # Write out the finished xml file
    with open(xml, "rb") as f:
        xmlf = open(working_dir + finished_fname, "w+b")
        xml_text = f.read()
        new_xml_text = re.sub(fulltext_pattern, replace_link, xml_text)
        xmlf.write(new_xml_text)
        xmlf.close()
    
    # Upload finished xml
    try:
        subprocess.check_call([DBUPLOADER_PATH, "upload", working_dir + finished_fname, DB_DIR + "/" + upload_folder + "/" + dirname + "/" + finished_fname])
    except Exception as e:
        print e
        print "Error uploading to dropbox!"
        print "Sending error report..."
        error_msg = "There was a problem uploading %s+_Output.xml to Dropbox.\n"\
                    "Full error follows:\n"\
                    "%s" % (dirname, e)
        email_failure(dirname + ".zip", error_msg)
        raise MyException("Dropbox upload error")


def email_success(dirname):
    """
    Email administrator a success message.
    Parameters:
        dirname: Name of unzipped ProQuest ETD directory
    """
    # Set up multipart message
    msg = MIMEMultipart()
    msg['Subject'] = '%s is ready for upload' % dirname
    msg['To'] = RESULT_EMAIL
    msg['From'] = "pi@localhost"
    msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'

    # Create and add body
    body = "%s/Output.xml is ready to be uploaded." % dirname
    part1 = MIMEText(body, 'plain')
    msg.attach(part1)

    # Send the email using SMTP
    s = smtplib.SMTP_SSL(SMTP_SERVER)
    s.login(SMTP_USER, SMTP_PASSWORD)
    s.sendmail("pi@localhost", RESULT_EMAIL, msg.as_string())
    s.quit()


def email_success_attachments(dirname, attachments):
    """
    Email administrator a success message with need for manual attachments.
    Parameters:
        dirname: Name of unzipped ProQuest ETD directory
    """
    # Set up multipart message
    msg = MIMEMultipart()
    msg['Subject'] = '%s requires manual intervention' % dirname
    msg['To'] = RESULT_EMAIL
    msg['From'] = "pi@localhost"
    msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'

    # Create and add body
    body = "%s/Output.xml is ready to be uploaded.\n" % dirname
    body += "Additionally the following files will need to be manually attached: \n"
    for att in attachments:
        body += os.path.basename(att) + "\n"
    part1 = MIMEText(body, 'plain')
    msg.attach(part1)

    # Send the email using SMTP
    s = smtplib.SMTP_SSL(SMTP_SERVER)
    s.login(SMTP_USER, SMTP_PASSWORD)
    s.sendmail("pi@localhost", RESULT_EMAIL, msg.as_string())
    s.quit()


def email_failure(culprit, message):
    """
    Email administrator a failure message.
    Parameters:
        culprit: Name of file that resulted in an error
        message: Full message detailing error
    """
    # Set up multipart message
    msg = MIMEMultipart()
    msg['Subject'] = 'Processing of %s FAILED!' % culprit
    msg['To'] = RESULT_EMAIL
    msg['From'] = "pi@localhost"
    msg.preamble = 'You will not see this in a MIME-aware mail reader.\n'

    # Create part from passed in message
    part1 = MIMEText(message, 'plain')
    msg.attach(part1)

    # Send the email using SMTP
    s = smtplib.SMTP_SSL(SMTP_SERVER)
    s.login(SMTP_USER, SMTP_PASSWORD)
    s.sendmail("pi@localhost", RESULT_EMAIL, msg.as_string())
    s.quit()


def poll_uploaddir(folder, seen_files):
    """
    Checks for new files in the upload dir.
    Parameters:
        seen_files: A list of already seen filepaths
    """
    before = dict ([(f, None) for f in seen_files if os.path.isfile(f)])
    after = dict ([(f, None) for f in listdir_fullpath(folder) if os.path.isfile(f)])
    added = [f for f in after if not f in before]
    if added: 
        print "Added: ", ", ".join (added)
        return added
    return None


def load_config():
    """
    Loads options from settings.conf into global variables.
    """
    global SLEEP_TIME
    global UPLOAD_DIR
    global DB_DIR
    global XSLT_PATH
    #global RESULT_EMAIL
    global SMTP_USER
    global SMTP_PASSWORD
    global SMTP_SERVER
    global DBUPLOADER_PATH

    global config
    config = ConfigParser.ConfigParser(allow_no_value=False)
    config.read('settings.conf')

    # Check that all options are present
    time_options = ['sleep_time']
    for option in time_options:
        if (not config.has_option('time', option)) or (config.get('time', option) == ''):
            print "Missing option in [time]: %s" % option
            sys.exit()
    dirs_options = ['upload_dir', 'dropbox_dir']
    for option in dirs_options:
        if (not config.has_option('dirs', option)) or (config.get('dirs', option) == ''):
            print "Missing option in [dirs]: %s" % option
            sys.exit()
    xslt_options = ['xslt_path']
    for option in xslt_options:
        if (not config.has_option('xslt', option)) or (config.get('xslt', option) == ''):
            print "Missing option in [xslt]: %s" % option
            sys.exit()
    smtp_options = ['smtp_server', 'smtp_user', 'smtp_password']
    for option in smtp_options:
        if (not config.has_option('smtp', option)) or (config.get('smtp', option) == ''):
            print "Missing option in [smtp]: %s" % option
            sys.exit()
    dropbox_options = ['dbuploader_path']
    for option in dropbox_options:
        if (not config.has_option('dropbox', option)) or (config.get('dropbox', option) == ''):
            print "Missing option in [dropbox]: %s" % option
            sys.exit()

    SLEEP_TIME = int(config.get('time', 'sleep_time'))
    UPLOAD_DIR = add_slash(config.get('dirs', 'upload_dir'))
    DB_DIR = add_slash(config.get('dirs', 'dropbox_dir'))
    XSLT_PATH = config.get('xslt', 'xslt_path')
    #RESULT_EMAIL = config.get('email', 'recipient_address')
    SMTP_SERVER = config.get('smtp', 'smtp_server')
    SMTP_USER = config.get('smtp', 'smtp_user')
    SMTP_PASSWORD = config.get('smtp', 'smtp_password')
    DBUPLOADER_PATH = config.get('dropbox', 'dbuploader_path')


def run_listener():
    seen_files_f = open(".seen.txt", "a+")
    seen_files = [line.strip() for line in seen_files_f.readlines()]
    with open(".broken.txt", "r") as b:
        seen_files += [line.strip() for line in b.readlines()]

    # Main run loop
    while True:
        # List of all subdirectories directly below the UPLOAD_DIR
        folders = [f for f in listdir_fullpath(UPLOAD_DIR) if os.path.isdir(f)]
        for folder in folders:
            global RESULT_EMAIL
            bname = os.path.basename(os.path.normpath(folder))
            if (not config.has_option('email', bname)) or (config.get('email', bname) == ''):
                print "No email confiugred for %s option in [email]" % bname
                print "Skipping this folder until one is configured."
                continue
            RESULT_EMAIL = config.get('email', bname)
            new = poll_uploaddir(folder, seen_files)
            if new != None:
                # There were new files. Unzip and process them.
                for new_f in new:
                    seen_files += [str(os.path.join(folder, new_f))]
                    seen_files_f.write(str(os.path.join(folder, new_f)) + "\n")

                    if new_f.split(".")[1] == "zip":
                        try:
                            unzipped_path = unzip(folder, new_f)
                            transform_files(unzipped_path)
                        except MyException as e:
                            # If we reach this point, one of the uploaded zips was not able to be processed.
                            # In this case we want to add it to .broken.txt so that the script can keep running while ignoring
                            # the file that caused the error.
                            print "There was a problem processing %s. An email has been sent detailing the issue." % (new_f)
                            print "Adding %s to .broken.txt. Please fix the issue, then remove the entry in .broken.txt!" % (new_f)
                            with open(".broken.txt", "a+") as b:
                                b.write(new_f + "\n")
                    else:
                        print "Non-zip file in upload directory!"

        time.sleep(SLEEP_TIME)


def main():
    load_config()
    run_listener()


if __name__ == '__main__':
    main()
