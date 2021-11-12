import unittest
from mock import patch, Mock
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
import dls_pmacremote
import socket

class TestTelnetInterface(unittest.TestCase):

    def setUp(self):
        self.obj = dls_pmacremote.PmacTelnetInterface()
