import socket
import unittest
from unittest.mock import Mock, patch

import dls_pmaclib.dls_pmacremote as dls_pmacremote


class TestEthernetInterface(unittest.TestCase):
    def setUp(self):
        self.obj = dls_pmacremote.PmacEthernetInterface()
        self.obj.hostname = "test"
        self.obj.port = 1234
        self.obj.verboseMode = False

    def test_init(self):
        assert self.obj.sock is None

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

    @patch("dls_pmaclib.dls_pmacremote.PmacEthernetInterface._sendCommand")
    @patch("socket.socket")
    def test_connects(self, mock_socket, mock_response):
        mock_response.return_value = "1.945  \r\x06"
        mock_instance = Mock()
        mock_instance.settimeout.return_value = None
        mock_instance.connect.return_value = None
        mock_socket.return_value = mock_instance
        assert self.obj.connect() is None
        assert mock_socket.called
        mock_instance.settimeout.assert_called_with(3.0)
        mock_instance.connect.assert_called_with(("test", 1234))
        mock_response.assert_called_with("i6=1 i3=2 ver")
        assert self.obj.isConnectionOpen is True

    @patch("dls_pmaclib.dls_pmacremote.PmacEthernetInterface.disconnect")
    @patch("dls_pmaclib.dls_pmacremote.PmacEthernetInterface._sendCommand")
    @patch("socket.socket")
    def test_incorrect_response(self, mock_socket, mock_response, mock_disconnect):
        mock_response.return_value = "incorrect"
        mock_instance = Mock()
        mock_instance.settimeout.return_value = None
        mock_instance.connect.return_value = None
        mock_socket.return_value = mock_instance
        ret = self.obj.connect()
        assert mock_socket.called
        mock_instance.settimeout.assert_called_with(3.0)
        mock_instance.connect.assert_called_with(("test", 1234))
        mock_response.assert_called_with("i6=1 i3=2 ver")
        assert mock_disconnect.called
        assert ret == 'Device did not respond correctly to a "ver" command'

    @patch("dls_pmaclib.dls_pmacremote.PmacEthernetInterface.disconnect")
    @patch("dls_pmaclib.dls_pmacremote.PmacEthernetInterface._sendCommand")
    @patch("socket.socket")
    def test_no_response(self, mock_socket, mock_sendcmd, mock_disconnect):
        mock_instance = Mock()
        mock_instance.settimeout.return_value = None
        mock_instance.connect.return_value = None
        mock_socket.return_value = mock_instance
        mock_sendcmd.side_effect = IOError
        ret = self.obj.connect()
        assert mock_socket.called
        mock_instance.settimeout.assert_called_with(3.0)
        mock_instance.connect.assert_called_with(("test", 1234))
        mock_sendcmd.assert_called_with("i6=1 i3=2 ver")
        assert mock_disconnect.called
        assert ret == 'Device failed to respond to a "ver" command'

    @patch("socket.socket")
    def test_unknown_host(self, mock_socket):
        mock_instance = Mock()
        mock_instance.settimeout.return_value = None
        mock_instance.connect.side_effect = socket.gaierror
        mock_socket.return_value = mock_instance
        self.obj.hostname = "unknown"
        assert self.obj.connect() == "ERROR: unknown host"
        assert mock_socket.called
        mock_instance.settimeout.assert_called_with(3.0)
        mock_instance.connect.assert_called_with(("unknown", 1234))

    @patch("socket.socket")
    def test_connection_error(self, mock_socket):
        mock_instance = Mock()
        mock_instance.settimeout.return_value = None
        mock_instance.connect.side_effect = Exception
        mock_socket.return_value = mock_instance
        ret = self.obj.connect()
        assert ret == "ERROR: connection refused by host"
        assert mock_socket.called
        mock_instance.settimeout.assert_called_with(3.0)
        mock_instance.connect.assert_called_with(("test", 1234))

    def test_disconnect_no_connection_open(self):
        self.obj.isConnectionOpen = False
        assert self.obj.disconnect() is None

    def test_disconnect_connection_open(self):
        self.obj.sock = Mock()
        self.obj.sock.close.return_value = None
        self.obj.isConnectionOpen = True
        self.obj.disconnect()
        assert self.obj.isConnectionOpen is False
        assert self.obj.sock.close.called

    def test_sendCommand_unexpected_terminator(self):
        self.obj.sock = Mock()
        attrs = {
            "settimeout.return_value": None,
            "sendall.return_value": "",
            "recv.return_value": b"response",
        }
        self.obj.sock.configure_mock(**attrs)
        expected_ret = "PMAC communication error: unexpected terminator"
        with self.assertRaises(OSError):
            assert self.obj._sendCommand("cmd") == expected_ret
        self.obj.sock.settimeout.assert_called_with(3.0)
        getresponseRequest_ret = b"@\xbf\x00\x00\x00\x00\x00\x03cmd"
        self.obj.sock.sendall.assert_called_with(getresponseRequest_ret)
        self.obj.sock.recv.assert_called_with(2048)

    def test_sendCommand(self):
        self.obj.sock = Mock()
        attrs = {
            "settimeout.return_value": None,
            "sendall.return_value": "",
            "recv.return_value": b"response\x0d",
        }
        self.obj.sock.configure_mock(**attrs)
        ret = self.obj._sendCommand("cmd")
        assert ret == "response\x0d"
        self.obj.sock.settimeout.assert_called_with(3.0)
        getresponseRequest_ret = b"@\xbf\x00\x00\x00\x00\x00\x03cmd"
        self.obj.sock.sendall.assert_called_with(getresponseRequest_ret)
        self.obj.sock.recv.assert_called_with(2048)
