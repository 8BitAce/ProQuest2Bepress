from difflib import context_diff
import glob
import os
import ProQuest2Bepress as P2B
import re
import shutil
import subprocess
import sys
import unittest

from collections import Counter

fulltext_pattern = re.compile(r'<fulltext-url>(.*)</fulltext-url>')
db_listing_pattern_1 = re.compile(r'')

class TestFileMethods(unittest.TestCase):

    def setUp(self):
        P2B.load_config()
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    def tearDown(self):
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    def addFiles(self):
        shutil.copy("./TestFiles/etdadmin_upload_362096.zip", P2B.UPLOAD_DIR)
        shutil.copy("./TestFiles/etdadmin_upload_362658.zip", P2B.UPLOAD_DIR)

    def test_poll_uploaddir(self):
        self.addFiles()
        self.assertEqual(Counter(P2B.poll_uploaddir([])), Counter([P2B.UPLOAD_DIR + 'etdadmin_upload_362096.zip', P2B.UPLOAD_DIR + 'etdadmin_upload_362658.zip']))

    def test_unzip(self):
        self.addFiles()
        path_result = P2B.unzip(P2B.UPLOAD_DIR + 'etdadmin_upload_362096.zip')
        self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + "etdadmin_upload_362096"))
        self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + "etdadmin_upload_362096/Shashe_ed.depaul_0937F_10005_DATA.xml"))
        self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + "etdadmin_upload_362096/Shashe_ed.depaul_0937F_10005.pdf"))


class TestTransformationMethods(unittest.TestCase):

    def setUp(self):
        P2B.load_config()
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    def tearDown(self):
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    def addFiles(self):
        shutil.copy("./TestFiles/etdadmin_upload_362096.zip", P2B.UPLOAD_DIR)
        shutil.copy("./TestFiles/etdadmin_upload_362658.zip", P2B.UPLOAD_DIR)

    def test_transform_files(self):
        self.addFiles()
        P2B.unzip(P2B.UPLOAD_DIR + 'etdadmin_upload_362096.zip')
        P2B.unzip(P2B.UPLOAD_DIR + 'etdadmin_upload_362658.zip')

        # Test etdadmin_upload_362096.zip
        print "Testing etdadmin_upload_362096.zip..."
        P2B.transform_files(P2B.UPLOAD_DIR + 'etdadmin_upload_362096/')
        self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + "etdadmin_upload_362096/etdadmin_upload_362096_Output.xml"))
        with open(P2B.UPLOAD_DIR + "etdadmin_upload_362096/etdadmin_upload_362096_Output.xml") as output_f:
            with open("./TestFiles/etdadmin_upload_362096_Output_Correct.xml") as correct_f:
                print "Testing etdadmin_upload_362096_Output.xml..."
                output_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in output_f.readlines()]
                correct_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in correct_f.readlines()]
                for line in context_diff(correct_text, output_text, fromfile='etdadmin_upload_362096_Output_Correct.xml', tofile='etdadmin_upload_362096_Output.xml'):
                    sys.stdout.write(line)
                self.assertEqual(output_text, correct_text)

        # Test etdadmin_upload_362658.zip
        print "Testing etdadmin_upload_362658.zip..."
        P2B.transform_files(P2B.UPLOAD_DIR + 'etdadmin_upload_362658/')
        self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + "etdadmin_upload_362658/etdadmin_upload_362658_Output.xml"))
        with open(P2B.UPLOAD_DIR + "etdadmin_upload_362658/etdadmin_upload_362658_Output.xml") as output_f:
            with open("./TestFiles/etdadmin_upload_362658_Output_Correct.xml") as correct_f:
                print "Testing etdadmin_upload_362658_Output.xml..."
                output_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in output_f.readlines()]
                correct_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in correct_f.readlines()]
                for line in context_diff(correct_text, output_text, fromfile='etdadmin_upload_362658_Output_Correct.xml', tofile='etdadmin_upload_362658_Output.xml'):
                    sys.stdout.write(line)
                self.assertEqual(output_text, correct_text)

        # Test Dropbox uploads
        print "Testing if everything is in Dropbox..."
        self.assertEqual(subprocess.check_output([P2B.DBUPLOADER_PATH, "list", P2B.DB_DIR + "etdadmin_upload_362096/"]), ' > Listing "/P2BTests/etdadmin_upload_362096/"... DONE\n [F] 2578    etdadmin_upload_362096_Output.xml\n [F] 2455004 Shashe_ed.depaul_0937F_10005.pdf\n')
        self.assertEqual(subprocess.check_output([P2B.DBUPLOADER_PATH, "list", P2B.DB_DIR + "etdadmin_upload_362658/"]), ' > Listing "/P2BTests/etdadmin_upload_362658/"... DONE\n [F] 2792    etdadmin_upload_362658_Output.xml\n [F] 58681   McCann Floeter 05212015 Electronic Theses and Disserations Approval Form.docx\n [F] 2006772 McCannFloeter_ed.depaul_0937F_10006.pdf\n')

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileMethods)
    unittest.TextTestRunner(verbosity=2).run(suite)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTransformationMethods)
    unittest.TextTestRunner(verbosity=2).run(suite)