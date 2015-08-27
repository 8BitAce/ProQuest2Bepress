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

class TestFileMethods(unittest.TestCase):

    def setUp(self):
        P2B.load_config()
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

        self.zip_files = [os.path.basename(f) for f in glob.glob("./TestFiles/*.zip")]
        self.etd_dirs = [os.path.splitext(os.path.basename(f))[0] for f in self.zip_files]

    def tearDown(self):
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    def addFiles(self):
        for zipf in self.zip_files:
            shutil.copy("./TestFiles/" + zipf, P2B.UPLOAD_DIR)

    def test_poll_uploaddir(self):
        self.addFiles()
        self.assertEqual(Counter(P2B.poll_uploaddir([])), Counter([P2B.UPLOAD_DIR + f for f in self.zip_files]))

    def test_unzip(self):
        self.addFiles()
        for i in range(len(self.zip_files)):
            path_result = P2B.unzip(P2B.UPLOAD_DIR + self.zip_files[i])
            self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + self.etd_dirs[i]))
            self.assertTrue(glob.glob(P2B.UPLOAD_DIR + self.etd_dirs[i] + "/*") is not None)


class TestTransformationMethods(unittest.TestCase):

    def setUp(self):
        P2B.load_config()
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

        self.zip_files = [os.path.basename(f) for f in glob.glob("./TestFiles/*.zip")]
        self.etd_dirs = [os.path.splitext(os.path.basename(f))[0] for f in self.zip_files]

    def tearDown(self):
        rm_files = glob.glob(P2B.UPLOAD_DIR + "*")
        for f in rm_files:
            if os.path.isfile(f):
                os.remove(f)
            elif os.path.isdir(f):
                shutil.rmtree(f)

    def addFiles(self):
        for zipf in self.zip_files:
            shutil.copy("./TestFiles/" + zipf, P2B.UPLOAD_DIR)

    def test_transform_files(self):
        self.addFiles()
        for zipf in self.zip_files:
            P2B.unzip(P2B.UPLOAD_DIR + zipf)

        # Test each zip
        for zipf in self.zip_files:
            if not os.path.exists("./TestFiles/" + os.path.splitext(zipf)[0] + "_Output.xml"):
                print "Missing correct output for %s. Skipping." % zipf
                continue

            print "Testing %s..." % zipf
            etd_name = os.path.splitext(zipf)[0]
            P2B.transform_files(P2B.UPLOAD_DIR + etd_name + '/')

            output_fname = etd_name + "_Output.xml"
            self.assertTrue(os.path.exists(P2B.UPLOAD_DIR + etd_name + "/" + output_fname))
            with open(P2B.UPLOAD_DIR + etd_name + "/" + output_fname) as output_f:
                with open("./TestFiles/" + output_fname) as correct_f:
                    print "Testing %s..." % output_fname
                    output_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in output_f.readlines()]
                    correct_text = [re.sub(fulltext_pattern, "<fulltext-url>LINK</fulltext-url>", line) for line in correct_f.readlines()]
                    for line in context_diff(correct_text, output_text):
                        sys.stdout.write(line)
                    self.assertEqual(output_text, correct_text)

        # Test Dropbox uploads
        print "Testing if everything is in Dropbox..."
        file_pattern = re.compile(r'\[F\]')
        for etd in self.etd_dirs:
            if not os.path.exists("./TestFiles/" + etd + "_Output.xml"):
                continue

            dbu_listing = subprocess.check_output([P2B.DBUPLOADER_PATH, "list", P2B.DB_DIR + etd])
            self.assertEqual(re.search(file_pattern, dbu_listing) != None, True)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFileMethods)
    unittest.TextTestRunner(verbosity=2).run(suite)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTransformationMethods)
    unittest.TextTestRunner(verbosity=2).run(suite)