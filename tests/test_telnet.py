import unittest
from mock import patch, Mock
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
import dls_pmacremote

class TestTelnetInterface(unittest.TestCase):

    def setUp(self):
        self.obj = dls_pmacremote.PmacTelnetInterface()
        self.obj.hostname = "hostname"
        self.obj.port = 123
        self.obj.verboseMode = False

    @patch("telnetlib.Telnet") 
    def test_hostname_not_set(self, mock_telnet):
        self.obj.hostname = None
        ret = self.obj.connect()
        assert mock_telnet.called
        assert ret == "ERROR: Could not open telnet session. No hostname set."

    @patch("dls_pmacremote.PmacTelnetInterface._sendCommand")
    @patch("telnetlib.Telnet") 
    def test_connects(self, mock_telnet, mock_sendcmd):
        ret = self.obj.connect()
        assert mock_telnet.called
        assert mock_sendcmd.called
        assert ret == None
        assert self.obj.isConnectionOpen == True

    @patch("dls_pmacremote.log")
    @patch("telnetlib.Telnet") 
    def test_connect_exception(self, mock_telnet, mock_log):
        mock_instance = Mock()
        mock_instance.open.side_effect = Exception
        mock_telnet.return_value = mock_instance
        ret = self.obj.connect()
        assert mock_telnet.called
        assert ret == ("ERROR: Could not open telnet session." + 
                        "\nException thrown: <class 'Exception'>")
        assert self.obj.isConnectionOpen == False

    def test_disconnect_no_connection_open(self):
        self.obj.isConnectionOpen = False
        assert self.obj.disconnect() == None

    @patch("telnetlib.Telnet") 
    def test_disconnect_connection_open(self, mock_connection):
        self.obj.isConnectionOpen = True
        self.obj.tn = mock_connection.return_value
        self.obj.disconnect()
        assert self.obj.isConnectionOpen == False

    @patch("telnetlib.Telnet") 
    def test_sendCommand(self, mock_telnet):
        self.obj.tn = Mock()
        attrs = {"sock_avail.return_value" : None,
        "read_very_eager.return_value" : None,
        "write.return_value" : None,
        "expect.return_value" : (0, None, "response\x0D".encode())}
        self.obj.tn.configure_mock(**attrs)
        ret = self.obj._sendCommand("cmd")
        assert ret == "response\x0D"
