import os
import unittest
from unittest.mock import patch

from dls_pmaclib.dls_pmcpreprocessor import ClsPmacParser


class TestPmcPreprocessor(unittest.TestCase):
    def setUp(self):
        self.test_file = "/tmp/test.txt"
        self.fh = open(self.test_file, "w")
        self.fh.write("This is a test.")
        self.fh.close()
        self.obj = ClsPmacParser()

    def test_parse(self):
        ret = self.obj.parse(pmcFileName=self.test_file)
        self.fh.close()
        assert ret == ["This is a test."]

    def test_save_output(self):
        self.obj.output = "0"
        ret = self.obj.saveOutput(self.test_file)
        f = open(self.test_file)
        assert f.read() == "0\n"
        f.close()
        assert ret == 0

    def tearDown(self):
        os.remove(self.test_file)


class TestPmcPreprocessorDefine(unittest.TestCase):
    def setUp(self):
        self.test_file = "/tmp/test.txt"
        self.fh = open(self.test_file, "w")
        self.fh.write("#define test P10\ntest = 1")
        self.fh.close()
        self.obj = ClsPmacParser()

    def test_parse_define(self):
        ret = self.obj.parse(pmcFileName=self.test_file)
        assert ret == ["", "P10 = 1"]

    def tearDown(self):
        os.remove(self.test_file)


class TestPmcPreprocessorInclude(unittest.TestCase):
    def setUp(self):
        self.include_file = "/tmp/test_include.py"
        self.fh = open(self.include_file, "w")
        self.fh.write("# This is a test.")
        self.fh.close()
        self.test_file = "/tmp/test.txt"
        self.f = open(self.test_file, "w")
        self.f.write("#include test_include")
        self.f.close()
        self.obj = ClsPmacParser()

    @patch("dls_pmaclib.dls_pmcpreprocessor.log")
    def test_parse_include(self, mock_log):
        ret = self.obj.parse(pmcFileName=self.test_file)
        assert ret == ["", ""]

    def tearDown(self):
        os.remove(self.include_file)
        os.remove(self.test_file)
