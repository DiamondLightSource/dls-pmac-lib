import unittest
from mock import patch, mock_open
from dls_pmcpreprocessor import ClsPmacParser
import io

class TestPmcPreprocessor(unittest.TestCase):

    pass
    """@patch("builtins.open")
    def test_parse_cannot_open_file(self, mock_open_file):
        mock_open_file.return_value.side_effect = OSError
        obj = ClsPmacParser()
        ret = obj.parse(pmcFileName="testfile", defines={})
        assert ret == []

    @patch("builtins.open")
    def test_parse(self, mock_open_file):
        obj = ClsPmacParser()
        ret = obj.parse(pmcFileName="testfile", defines={})
        print(ret)
        #assert"""

    '''def test_parse_with_include(self):
        test_file = TemporaryFile()
        testdef = {"test" : "something"}
        #with open(test_file, 'w') as f:  
        test_file.write(b"#include test")
        obj = ClsPmacParser()
        ret = obj.parse(pmcFileName=test_file, defines=testdef)
        test_file.close()
        assert ret == [""]

    def test_substitute_macros(self):
        test_dict = {"test" : "substitution"}
        test_text = "This is a test"
        obj = ClsPmacParser()
        actual_return = obj.substitute_macros(test_dict, test_text)
        expected_return = "This is a substitution"
        self.assertEqual(actual_return,expected_return)

    def test_save_output(self):
        obj = ClsPmacParser()
        obj.output = "This is a test"
        outfile = "test_save_output.txt"
        ret = obj.saveOutput(outputFile=outfile)
        assert ret == 0
        os.remove(outfile) # delete file'''
