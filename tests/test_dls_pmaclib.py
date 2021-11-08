import unittest
import io
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
from dls_pmaclib import HelloClass, say_hello_lots
from cli import main

class DlsControlTest(unittest.TestCase):

    def test_hello_class_formats_greeting(self):
        obj = HelloClass("test")
        assert obj.format_greeting() == "Hello test"

    def test_hello_lots_defaults(self):
        capOutput = io.StringIO()
        sys.stdout = capOutput
        say_hello_lots()
        sys.stdout = sys.__stdout__
        assert capOutput.getvalue() == "Hello me\n" * 5

    def test_cli(self):
        capOutput = io.StringIO()
        sys.stdout = capOutput
        main(["person", "--times=2"])        
        sys.stdout = sys.__stdout__
        assert capOutput.getvalue() == "Hello person\n" * 2
