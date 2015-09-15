from difflib import context_diff
import glob
import os
import ProQuest2Bepress as P2B
import re
import shutil
import subprocess
import sys
import unittest


# Pattern to match the fulltext-url element in xml
fulltext_pattern = re.compile(r'<fulltext-url>(.*)</fulltext-url>')

def listdir_fullpath(d):
    """
    Returns directory listing with FULL paths.
    Parameters:
        d: The directory to list.
    """
    return [os.path.join(d, f) for f in os.listdir(d)]


class TestFileMethods(unittest.TestCase):

    # Called before each test is run.
    def setUp(self):
        # Read in the config values. We'll need them.
        P2B.load_config()

        # Remove everything from the UPLOAD_DIR
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

        self.test_dirs = [f for f in listdir_fullpath("./TestFiles/") if os.path.isdir(f)]
        self.zip_files = dict()
        self.etd_dirs = dict()
        for test_dir in self.test_dirs:
            # Get a list of the filename of every zip file in ./TestFiles/
            self.zip_files[test_dir] = [os.path.basename(f) for f in listdir_fullpath(test_dir) if os.path.isfile(f)]
            # Get a list of the basenames of every etd
            self.etd_dirs[test_dir] = [os.path.splitext(os.path.basename(f))[0] for f in self.zip_files[test_dir]]

    # Called after each test finishes
    def tearDown(self):
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    # Copy each zip from ./TestFiles/ to UPLOAD_DIR
    def addFiles(self):
        for test_dir in self.test_dirs:
            shutil.copytree(test_dir, P2B.UPLOAD_DIR + os.path.basename(os.path.normpath(test_dir)))

    def test_poll_uploaddir(self):
        self.addFiles()
        for test_dir in self.test_dirs:
            upload_dir = os.path.join(P2B.UPLOAD_DIR, os.path.basename(test_dir)) + os.sep
            # Check that poll_uploaddir() reports all the files have been added
            list1 = P2B.poll_uploaddir(upload_dir, [])
            list2 = [os.path.join(upload_dir, f) for f in self.zip_files[test_dir]]
            self.assertTrue(len(list1) == len(list2) and sorted(list1) == sorted(list2))

    def test_unzip(self):
        self.addFiles()
        for test_dir in self.test_dirs:
            upload_dir = os.path.join(P2B.UPLOAD_DIR, os.path.basename(test_dir)) + os.sep
            for i in range(len(self.zip_files[test_dir])):
                P2B.unzip(upload_dir, upload_dir + self.zip_files[test_dir][i])
                # Check that a new directory was made for the etd
                self.assertTrue(os.path.exists(upload_dir + self.etd_dirs[test_dir][i]))
                # Check that there are files present in the newly created directory
                self.assertTrue(glob.glob(P2B.UPLOAD_DIR + self.etd_dirs[test_dir][i] + "/*") is not None)


class TestTransformationMethods(unittest.TestCase):

    # Called before each test is run.
    def setUp(self):
        # Read in the config values. We'll need them.
        P2B.load_config()

        # Remove everything from the UPLOAD_DIR
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

        self.test_dirs = [f for f in listdir_fullpath("./TestFiles/") if os.path.isdir(f)]
        self.zip_files = dict()
        self.etd_dirs = dict()
        for test_dir in self.test_dirs:
            # Get a list of the filename of every zip file in ./TestFiles/
            self.zip_files[test_dir] = [os.path.basename(f) for f in listdir_fullpath(test_dir) if os.path.isfile(f)]
            # Get a list of the basenames of every etd
            self.etd_dirs[test_dir] = [os.path.splitext(os.path.basename(f))[0] for f in self.zip_files[test_dir]]

    # Called after each test finishes
    def tearDown(self):
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    # Copy each zip from ./TestFiles/ to UPLOAD_DIR
    def addFiles(self):
        for test_dir in self.test_dirs:
            shutil.copytree(test_dir, P2B.UPLOAD_DIR + "/" + os.path.basename(os.path.normpath(test_dir)))

    def test_transform_files(self):
        self.addFiles()

        for test_dir in self.test_dirs:
            # TODO: This logic really shouldn't have to be in the tests.
            bname = os.path.basename(os.path.normpath(test_dir))
            if (not P2B.config.has_option('email', bname)) or (P2B.config.get('email', bname) == ''):
                print "No email confiugred for %s option in [email]" % bname
                print "Skipping this folder until one is configured."
                continue
            P2B.RESULT_EMAIL = P2B.config.get('email', bname)

            upload_dir = os.path.join(P2B.UPLOAD_DIR, os.path.basename(test_dir)) + os.sep

            # Unzip each zip file
            for zipf in self.zip_files[test_dir]:
                P2B.unzip(upload_dir, upload_dir + zipf)

            # Test each zip
            for zipf in self.zip_files[test_dir]:
                # If the correct output for a zip is not present we should skip it
                if not os.path.exists("./TestFiles/" + os.path.splitext(zipf)[0] + "_Output.xml"):
                    print "Missing correct output for %s. Skipping." % zipf
                    continue

                print "Testing %s..." % zipf
                etd_name = os.path.splitext(zipf)[0]
                P2B.transform_files(upload_dir + etd_name + '/')

                output_fname = etd_name + "_Output.xml"
                self.assertTrue(os.path.exists(upload_dir + etd_name + "/" + output_fname))
                with open(upload_dir + etd_name + "/" + output_fname) as output_f:
                    with open("./TestFiles/" + output_fname) as correct_f:
                        print "Testing %s..." % output_fname
                        # The generated link will be different each time so we should replace it with something standard
                        output_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in output_f.readlines()]
                        correct_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in correct_f.readlines()]
                        # Do a diff of the generated file and the correct output
                        for line in context_diff(correct_text, output_text):
                            sys.stdout.write(line)
                        # Check if the generated output matches the correct output
                        self.assertEqual(output_text, correct_text)

            # Test Dropbox uploads
            print "Testing if everything is in Dropbox..."
            file_pattern = re.compile(r'\[F\]')
            for etd in self.etd_dirs[test_dir]:
                # If the correct output for a zip is not present we should skip it
                if not os.path.exists("./TestFiles/" + etd + "_Output.xml"):
                    continue

                dbu_listing = subprocess.check_output([P2B.DBUPLOADER_PATH, "list", P2B.DB_DIR + bname + "/" + etd +  "/"])
                self.assertEqual(re.search(file_pattern, dbu_listing) != None, True)

if __name__ == '__main__':
    print "WARNING: This test suite WILL remove everything from the configured directories!"
    response = raw_input("Really continue? (y/n) ")
    if response == "y":
        suite = unittest.TestLoader().loadTestsFromTestCase(TestFileMethods)
        unittest.TextTestRunner(verbosity=2).run(suite)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestTransformationMethods)
        unittest.TextTestRunner(verbosity=2).run(suite)