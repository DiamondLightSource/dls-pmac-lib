import unittest
from mock import patch, Mock
import sys

sys.path.append("/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib")
import dls_pmacremote
import socket


class TestEthernetInterface(unittest.TestCase):
    def setUp(self):
        self.obj = dls_pmacremote.PmacEthernetInterface()
        self.obj.hostname = "test"
        self.obj.port = 1234
        self.obj.verboseMode = False

    def test_connection_already_open(self):
        self.obj.isConnectionOpen = True
        ret = self.obj.connect()
        assert ret == "Socket is already open"

    def test_hostname_not_set(self):
        self.obj.hostname = None
        ret = self.obj.connect()
        assert ret == "ERROR: hostname or port number not set"

    def test_port_not_set(self):
        self.obj.port = None
        ret = self.obj.connect()
        assert ret == "ERROR: hostname or port number not set"

    @patch(
        "dls_pmacremote.PmacEthernetInterface._sendCommand",
        return_value="1.945  \r\x06",
    )
    @patch("socket.socket")
    def test_connects(self, mock_socket, mock_response):
        self.obj.connect()
        assert mock_socket.called
        assert mock_response.called
        assert self.obj.isConnectionOpen == True

    @patch(
        "dls_pmacremote.PmacEthernetInterface._sendCommand", return_value="incorrect"
    )
    @patch("socket.socket")
    def test_incorrect_response(self, mock_socket, mock_response):
        ret = self.obj.connect()
        assert mock_socket.called
        assert mock_response.called
        assert self.obj.isConnectionOpen == False
        assert ret == 'Device did not respond correctly to a "ver" command'

    @patch("dls_pmacremote.PmacEthernetInterface._sendCommand")
    @patch("socket.socket")
    def test_no_response(self, mock_socket, mock_sendcmd):
        mock_sendcmd.side_effect = IOError
        ret = self.obj.connect()
        expected_return = 'Device failed to respond to a "ver" command'
        assert mock_socket.called
        self.assertEqual(ret, expected_return)
        assert self.obj.isConnectionOpen == False

    @patch("socket.socket")
    def test_unknown_host(self, mock_socket):
        mock_instance = Mock()
        mock_instance.connect.side_effect = socket.gaierror
        mock_socket.return_value = mock_instance
        self.obj.hostname = "unknown"
        ret = self.obj.connect()
        assert mock_socket.called
        assert ret == "ERROR: unknown host"

    @patch("socket.socket")
    def test_connection_error(self, mock_socket):
        mock_instance = Mock()
        mock_instance.connect.side_effect = Exception
        mock_socket.return_value = mock_instance
        ret = self.obj.connect()
        assert mock_socket.called
        assert ret == "ERROR: connection refused by host"

    def test_sendCommand_unexpected_terminator(self):
        self.obj.sock = Mock()
        attrs = {
            "settimeout.return_value": None,
            "sendall.return_value": "",
            "recv.return_value": "response".encode(),
        }
        self.obj.sock.configure_mock(**attrs)
        with self.assertRaises(OSError):
            ret = self.obj._sendCommand("cmd")

    def test_sendCommand(self):
        self.obj.sock = Mock()
        attrs = {
            "settimeout.return_value": None,
            "sendall.return_value": "",
            "recv.return_value": "response\x0D".encode(),
        }
        self.obj.sock.configure_mock(**attrs)
        ret = self.obj._sendCommand("cmd")
        assert ret == "response\x0D"

    def test_disconnect_no_connection_open(self):
        self.obj.isConnectionOpen = False
        ret = self.obj.disconnect()
        assert ret == None

    @patch("socket.socket")
    def test_disconnect_connection_open(self, mock_socket):
        self.obj.isConnectionOpen = True
        self.obj.sock = mock_socket.return_value
        self.obj.disconnect()
        assert self.obj.isConnectionOpen == False
