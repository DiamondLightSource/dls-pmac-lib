import unittest
import re
from mock import patch, Mock
import sys

sys.path.append("/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib")
import dls_pmacremote
import serial


class TestSerialInterface(unittest.TestCase):
    def setUp(self):
        self.obj = dls_pmacremote.PmacSerialInterface()
        self.obj.hostname = "hostname"
        self.obj.port = 1234
        self.obj.verboseMode = False

    def test_init(self):
        assert len(self.obj.lstRegExps) == 5

    @patch("dls_pmacremote.PmacSerialInterface._sendCommand")
    @patch("serial.Serial")
    def test_connects(self, mock_serial, mock_sendcmd):
        assert self.obj.connect() == None
        assert self.obj.baud_rate == 1234
        assert self.obj.comm_port == "hostname"
        assert self.obj.last_received_packet == ""
        assert self.obj.last_comm_time == 0.0
        assert self.obj.n_timeouts == 0
        mock_serial.assert_called_with(
            "hostname", 1234, timeout=3.0, rtscts=True, dsrdtr=True
        )
        mock_sendcmd.assert_called_with("ver")
        assert self.obj.isConnectionOpen == True

    @patch("serial.Serial")
    def test_connection_already_open(self, mock_serial):
        self.obj.isConnectionOpen = True
        ret = self.obj.connect()
        assert ret == "Socket is already open"
        assert self.obj.baud_rate == 1234
        assert self.obj.comm_port == "hostname"
        assert self.obj.last_received_packet == ""
        assert self.obj.last_comm_time == 0.0
        assert self.obj.n_timeouts == 0
        mock_serial.assert_called_with(
            "hostname", 1234, timeout=3.0, rtscts=True, dsrdtr=True
        )

    @patch("serial.Serial")
    def test_port_in_use(self, mock_serial):
        mock_serial.side_effect = serial.serialutil.SerialException
        ret = self.obj.connect()
        assert ret == "Port already in use!"
        assert self.obj.baud_rate == 1234
        assert self.obj.comm_port == "hostname"
        assert self.obj.last_received_packet == ""
        assert self.obj.last_comm_time == 0.0
        assert self.obj.n_timeouts == 0
        mock_serial.assert_called_with(
            "hostname", 1234, timeout=3.0, rtscts=True, dsrdtr=True
        )
        assert self.obj.isConnectionOpen == False

    @patch("dls_pmacremote.PmacSerialInterface._sendCommand")
    @patch("serial.Serial")
    def test_connect_io_error(self, mock_serial, mock_sendcmd):
        mock_sendcmd.side_effect = IOError
        with self.assertRaises(IOError):
            assert self.obj.connect() == None
        assert self.obj.baud_rate == 1234
        assert self.obj.comm_port == "hostname"
        assert self.obj.last_received_packet == ""
        assert self.obj.last_comm_time == 0.0
        assert self.obj.n_timeouts == 0
        mock_serial.assert_called_with(
            "hostname", 1234, timeout=3.0, rtscts=True, dsrdtr=True
        )
        mock_sendcmd.assert_called_with("ver")
        assert self.obj.isConnectionOpen == False

    def test_disconnect_no_connection_open(self):
        assert self.obj.disconnect() == None

    def test_disconnect_connection_open(self):
        self.obj.serial = Mock()
        self.obj.isConnectionOpen = True
        assert self.obj.disconnect() == None
        assert self.obj.isConnectionOpen == False
        assert self.obj.serial.close.called

    @patch("dls_pmacremote.log")
    def test_sendCommand_timeout(self, mock_log):
        self.obj.timeout = 0.5
        self.obj.n_timeouts = 0
        self.obj.serial = Mock()
        attrs = {
            "inWaiting.return_value": False,
            "write.return_value": None,
            "read.return_value": "response".encode(),
        }
        self.obj.serial.configure_mock(**attrs)
        ret = self.obj._sendCommand("cmd")
        self.assertRegex(ret, "^(response)+$")
        self.obj.serial.write.assert_called_with("\r")
        assert self.obj.serial.inWaiting.called
        assert self.obj.serial.read.called
        assert self.obj.n_timeouts == 1
