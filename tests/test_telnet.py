import unittest

import dls_pmaclib.dls_pmacremote as dls_pmacremote
from mock import Mock, patch


class TestTelnetInterface(unittest.TestCase):
    def setUp(self):
        self.obj = dls_pmacremote.PmacTelnetInterface()
        self.obj.hostname = "hostname"
        self.obj.port = 123
        self.obj.verboseMode = False

    def test_init(self):
        assert self.obj.tn is None
        assert len(self.obj.lstRegExps) == 5

    @patch("telnetlib.Telnet")
    def test_hostname_not_set(self, mock_telnet):
        self.obj.hostname = None
        ret = self.obj.connect()
        assert mock_telnet.called
        assert ret == "ERROR: Could not open telnet session. No hostname set."

    @patch("dls_pmaclib.dls_pmacremote.PmacTelnetInterface._sendCommand")
    @patch("telnetlib.Telnet")
    def test_connects(self, mock_telnet, mock_sendcmd):
        mock_instance = Mock()
        mock_instance.open.return_value = None
        mock_telnet.return_value = mock_instance
        ret = self.obj.connect()
        assert mock_telnet.called
        mock_instance.open.assert_called_with("hostname", 123)
        mock_sendcmd.assert_called_with("ver")
        assert ret is None
        assert self.obj.isConnectionOpen is True

    @patch("dls_pmaclib.dls_pmacremote.log")
    @patch("telnetlib.Telnet")
    def test_connect_exception(self, mock_telnet, mock_log):
        mock_instance = Mock()
        mock_instance.open.side_effect = Exception
        mock_instance.close.return_value = None
        mock_telnet.return_value = mock_instance
        ret = self.obj.connect()
        assert mock_telnet.called
        mock_instance.open.assert_called_with("hostname", 123)
        assert mock_instance.close.called
        assert ret == (
            "ERROR: Could not open telnet session."
            + "\nException thrown: <class 'Exception'>"
        )
        assert self.obj.isConnectionOpen is False

    def test_disconnect_no_connection_open(self):
        self.obj.isConnectionOpen = False
        assert self.obj.disconnect() is None

    @patch("telnetlib.Telnet")
    def test_disconnect_connection_open(self, mock_connection):
        self.obj.isConnectionOpen = True
        self.obj.tn = mock_connection.return_value
        self.obj.disconnect()
        assert self.obj.tn.close.called
        assert self.obj.isConnectionOpen is False

    @patch("telnetlib.Telnet")
    def test_sendCommand(self, mock_telnet):
        self.obj.tn = Mock()
        attrs = {
            "sock_avail.return_value": False,
            "read_very_eager.return_value": None,
            "write.return_value": None,
            "expect.return_value": (0, None, "response\x0D".encode()),
        }
        self.obj.tn.configure_mock(**attrs)
        ret = self.obj._sendCommand("cmd")
        assert ret == "response\x0D"
        assert self.obj.tn.sock_avail.called
        self.obj.tn.write.assert_called_with("cmd\r\n".encode("utf8"))
        self.obj.tn.expect.assert_called_with(self.obj.lstRegExps, 3.0)
