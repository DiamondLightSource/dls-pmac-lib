import unittest
import re
from mock import patch, Mock
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
import dls_pmacremote
import serial

class TestSerialInterface(unittest.TestCase):

    def setUp(self):
        self.obj = dls_pmacremote.PmacSerialInterface()
        self.obj.hostname = "hostname"
        self.obj.port = 1234
        self.obj.verboseMode = False

    @patch("dls_pmacremote.PmacSerialInterface._sendCommand")
    @patch("serial.Serial")
    def test_connects(self, mock_serial, mock_sendcmd):
        ret = self.obj.connect()
        assert mock_serial.called
        assert mock_sendcmd.called
        assert ret == None
        assert self.obj.isConnectionOpen == True

    @patch("serial.Serial")
    def test_connection_already_open(self, mock_serial):
        self.obj.isConnectionOpen = True
        ret = self.obj.connect()
        assert ret == "Socket is already open"

    @patch("serial.Serial")
    def test_port_in_use(self, mock_serial):
        mock_serial.side_effect = serial.serialutil.SerialException
        ret = self.obj.connect()
        assert ret == "Port already in use!"

    @patch("dls_pmacremote.PmacSerialInterface._sendCommand")
    @patch("serial.Serial")
    def test_connect_io_error(self, mock_serial, mock_sendcmd):
        mock_sendcmd.side_effect = IOError
        self.obj.isConnectionOpen = False
        with self.assertRaises(IOError):
            self.obj.connect()
        assert self.obj.isConnectionOpen == False

    def test_disconnect_no_connection_open(self):
        self.obj.isConnectionOpen = False
        ret = self.obj.disconnect()
        assert ret == None

    @patch("serial.Serial")
    def test_disconnect_connection_open(self, mock_serial):
        self.obj.isConnectionOpen = True
        self.obj.serial = mock_serial.return_value
        self.obj.disconnect()
        assert self.obj.isConnectionOpen == False

    @patch("dls_pmacremote.log")
    def test_sendCommand_timeout(self, mock_log):
        self.obj.timeout = 0.5
        self.obj.n_timeouts = 0
        self.obj.serial = Mock()
        attrs = {"inWaiting.return_value" : False,
        "readLine.return_value" : None,
        "write.return_value" : None,
        "read.return_value" : "response".encode()}
        self.obj.serial.configure_mock(**attrs)
        ret = self.obj._sendCommand("cmd")
        self.assertRegex(ret,"^(response)+$")
        assert self.obj.n_timeouts == 1
