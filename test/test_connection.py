import unittest
from mock import patch, Mock
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
import dls_pmacremote
import paramiko
import socket
import serial

class TestRemotePmacInterface(unittest.TestCase):

    def test_setConnectionParams(self):
        obj = dls_pmacremote.RemotePmacInterface()
        obj.setConnectionParams()
        assert obj.hostname == "localhost"
        assert obj.port == None

    @patch("dls_pmacremote.RemotePmacInterface")
    def test_sendCommand(self, mock_sendcmd):
        mock_instance = Mock()
        mock_instance._sendCommand.side_effect = NotImplementedError
        mock_sendcmd.return_value = mock_instance
        obj = dls_pmacremote.RemotePmacInterface()
        with self.assertRaises(NotImplementedError):
            obj._sendCommand("command")

class TestSshConnection(unittest.TestCase):

    def test_connection_already_open(self):
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = True
        actual_return = obj.connect()
        expected_return = "Already connected"
        self.assertEqual(actual_return, expected_return)

    def test_hostname_not_set(self):
        obj = dls_pmacremote.PPmacSshInterface()
        obj.hostname = None
        actual_return = obj.connect()
        expected_return = "ERROR: hostname not set"
        self.assertEqual(actual_return, expected_return)

    # when obj.connect() called, SSHClient object is initialised 
    @patch("dls_pmacremote.PPmacSshInterface.sendCommand", return_value = (None,None))
    @patch("dls_pmacremote.PPmacSshInterface.start_gpascii")
    @patch("paramiko.client.SSHClient.connect")
    def test_connects(self, mock_connect, mock_gpascii, mock_sendcmd):
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = False
        obj.hostname = 'test'
        obj.port = 22
        obj.connect()
        assert mock_connect.called
        assert mock_gpascii.called
        assert mock_sendcmd.called
        actual_result = obj.isConnectionOpen
        expected_result = True
        self.assertEqual(actual_result, expected_result)

    @patch("paramiko.client.SSHClient.connect")
    def test_wrong_username_password(self, mock_connect):
        mock_connect.side_effect = paramiko.ssh_exception.AuthenticationException
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = False
        obj.hostname = 'test'
        obj.port = 22
        actual_return = obj.connect(username="incorrect", password="incorrect")
        expected_return = "Invalid username or password"
        self.assertEqual(actual_return, expected_return)

    @patch("paramiko.client.SSHClient.connect")
    def test_connection_error(self, mock_connect):
        mock_connect.side_effect = Exception()
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = False
        obj.hostname = 'test'
        obj.port = 22
        actual_return = obj.connect(username="incorrect")
        expected_return = "Cannot connect to test 22"
        self.assertEqual(actual_return, expected_return)

    @patch("paramiko.client.SSHClient.connect")
    def test_port_not_set(self, mock_connect):
        mock_connect.side_effect = Exception()
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = False
        obj.hostname = 'test'
        actual_return = obj.connect()
        expected_return = "Cannot connect to test None"
        self.assertEqual(actual_return, expected_return)

    def test_disconnect_no_connection_open(self):
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = False
        actual_return = obj.disconnect()
        assert actual_return == None

    @patch("paramiko.client.SSHClient")
    def test_disconnect_connection_open(self, mock_client):
        obj = dls_pmacremote.PPmacSshInterface()
        obj.isConnectionOpen = True
        obj.client = mock_client.return_value
        obj.disconnect()
        assert obj.isConnectionOpen == False

    #@patch("paramiko.client.SSHClient.invoke_shell")
    #def _sendCommand(self):#, mock_client):
        #obj = dls_pmacremote.PPmacSshInterface()
        #obj.gpascii_client = mock_client.return_value
        #obj._sendCommand("command")

    '''def test_get_file(self):
        fake_file = io.StringIO("contents")
        my_directory = ""
        obj = dls_pmacremote.PPmacSshInterface()
        obj.getFile(fake_file,my_directory)'''


    #def test_put_file()

    #def test_send_ssh_command()
    #@patch("paramiko.client.SSHClient.exec_command")
    #@patch("paramiko.client.SSHClient")
    #def test_send_ssh_command(self, mock_client, mock_cmd):
     #   obj = dls_pmacremote.PPmacSshInterface()
      #  obj.sendSshCommand("cmd")

    def test_get_pmac_model(self):
        obj = dls_pmacremote.PPmacSshInterface()
        obj._pmacModelName = 'name'
        actual_return = obj.getPmacModel()
        assert actual_return == 'name'

    @patch("dls_pmacremote.PPmacSshInterface.getPmacModelCode", return_value=604020)
    def test_get_pmac_model_is_none(self, mock_get_pmac_model_name):
        obj = dls_pmacremote.PPmacSshInterface()
        obj._pmacModelName = None
        actual_return = obj.getPmacModel()
        assert actual_return == "Power PMAC UMAC"

    @patch("dls_pmacremote.PPmacSshInterface.getPmacModelCode", return_value=0)
    def test_get_pmac_model_unsupported(self, mock_get_model_code):
        obj = dls_pmacremote.PPmacSshInterface()
        obj._pmacModelName = None
        with self.assertRaises(ValueError):
            obj.getPmacModel()
        assert obj._pmacModelName == None

    @patch("dls_pmacremote.PPmacSshInterface.sendCommand", return_value = (5,True))
    def test_get_number_axes(self, mock_sendcmd):
        obj = dls_pmacremote.PPmacSshInterface()
        actual_return = obj.getNumberOfAxes()
        expected_return = 4
        self.assertEqual(actual_return, expected_return)

class TestEthernetConnection(unittest.TestCase):

    def test_connection_already_open(self):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.isConnectionOpen = True
        actual_return = obj.connect()
        expected_return = "Socket is already open"
        self.assertEqual(actual_return, expected_return)

    def test_hostname_not_set(self):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = None
        obj.port = 1234
        actual_return = obj.connect()
        expected_return = "ERROR: hostname or port number not set"
        self.assertEqual(actual_return, expected_return)

    def test_port_not_set(self):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = 'test'
        obj.port = None
        actual_return = obj.connect()
        expected_return = "ERROR: hostname or port number not set"
        self.assertEqual(actual_return, expected_return)

    @patch("dls_pmacremote.PmacEthernetInterface._sendCommand", return_value="1.945  \r\x06")
    @patch("socket.socket")
    def test_connects(self, mock_socket, mock_response):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = 'test'
        obj.port = 1234
        obj.connect()
        assert mock_socket.called
        assert mock_response.called
        assert obj.isConnectionOpen == True

    @patch("dls_pmacremote.PmacEthernetInterface._sendCommand", return_value="incorrect")
    @patch("socket.socket")
    def test_incorrect_response(self, mock_socket, mock_response):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = 'test'
        obj.port = 1234
        actual_return = obj.connect()
        assert mock_socket.called
        assert mock_response.called
        assert obj.isConnectionOpen == False
        expected_return = 'Device did not respond correctly to a "ver" command'
        self.assertEqual(actual_return, expected_return)

    #calling _sendCommand
    """@patch("dls_pmacremote.PmacEthernetInterface._sendCommand")
    @patch("socket.socket")
    def test_no_response(self, mock_socket, mock_sendcmd):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = 'test'
        obj.port = 1234
        actual_return = obj.connect()
        expected_return = 'Device failed to respond to a "ver" command'
        assert mock_socket.called
        self.assertEqual(actual_return, expected_return)"""

    '''@patch("socket.socket.connect")
    @patch("socket.socket")
    def test_unknown_host(self, mock_socket, mock_connect):
        mock_connect.side_effect = socket.gaierror
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = 'unknown'
        obj.port = 1234
        actual_return = obj.connect()
        expected_return = "ERROR: unknown host"
        assert mock_socket.called
        self.assertEqual(actual_return, expected_return)

    @patch("socket.socket.connect")
    @patch("socket.socket")
    def test_connection_error(self, mock_socket, mock_connect):
        mock_connect.side_effect = Exception
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.hostname = 'host'
        obj.port = 1234
        actual_return = obj.connect()
        expected_return = "ERROR: connection refused by host"
        assert mock_socket.called
        self.assertEqual(actual_return, expected_return)

    @patch("socket.socket.recv")
    @patch("socket.socket.sendall")
    @patch("socket.socket")
    def test_sendCommand(self, mock_socket, mock_sendall, mock_recv):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.sock = mock_socket.return_value
        with self.assertRaises(OSError):
            obj._sendCommand("cmd")'''

    def test_disconnect_no_connection_open(self):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.isConnectionOpen = False
        actual_return = obj.disconnect()
        assert actual_return == None

    @patch("socket.socket")
    def test_disconnect_connection_open(self, mock_socket):
        obj = dls_pmacremote.PmacEthernetInterface()
        obj.isConnectionOpen = True
        obj.sock = mock_socket.return_value
        obj.disconnect()
        assert obj.isConnectionOpen == False

class TestTelnetConnection(unittest.TestCase):

    @patch("telnetlib.Telnet") 
    def test_hostname_not_set(self, mock_telnet):
        obj = dls_pmacremote.PmacTelnetInterface()
        obj.hostname = None
        actual_return = obj.connect()
        assert mock_telnet.called
        expected_return = "ERROR: Could not open telnet session. No hostname set."
        self.assertEqual(actual_return, expected_return)

    @patch("dls_pmacremote.PmacTelnetInterface._sendCommand")
    @patch("telnetlib.Telnet") 
    def test_connects(self, mock_telnet, mock_sendcmd):
        obj = dls_pmacremote.PmacTelnetInterface()
        obj.hostname = 'hostname'
        obj.port = 123
        actual_return = obj.connect()
        assert mock_telnet.called
        assert mock_sendcmd.called
        actual_result = obj.isConnectionOpen
        expected_return = None
        expected_result = True
        self.assertEqual(actual_return, expected_return)
        self.assertEqual(actual_result, expected_result)

    def test_disconnect_no_connection_open(self):
        obj = dls_pmacremote.PmacTelnetInterface()
        obj.isConnectionOpen = False
        actual_return = obj.disconnect()
        assert actual_return == None

    @patch("telnetlib.Telnet") 
    def test_disconnect_connection_open(self, mock_connection):
        obj = dls_pmacremote.PmacTelnetInterface()
        obj.isConnectionOpen = True
        obj.tn = mock_connection.return_value
        obj.disconnect()
        assert obj.isConnectionOpen == False

    #def test_sendCommand()
    '''@patch("telnetlib.Telnet.expect", return_value = (-1,None,""))
    @patch("telnetlib.Telnet.write")
    @patch("telnetlib.Telnet.read_very_eager") 
    @patch("telnetlib.Telnet.sock_avail") 
    @patch("telnetlib.Telnet") 
    def test_sendCommand(self, mock_telnet, mock_tn_avail, mock_tn_rve, 
                mock_tn_write, mock_tn_expect):
        obj = dls_pmacremote.PmacTelnetInterface()
        obj.tn = mock_telnet.return_value
        obj._sendCommand("cmd")'''

class TestSerialConnection(unittest.TestCase):

    @patch("dls_pmacremote.PmacSerialInterface._sendCommand")
    @patch("serial.Serial")
    def test_connects(self, mock_serial, mock_sendcmd):
        obj = dls_pmacremote.PmacSerialInterface()
        obj.hostname = 'hostname'
        obj.port = 1234
        actual_return = obj.connect()
        assert mock_serial.called
        assert mock_sendcmd.called
        actual_result = obj.isConnectionOpen
        assert actual_return == None
        assert actual_result == True

    @patch("serial.Serial")
    def test_connection_already_open(self, mock_serial):
        obj = dls_pmacremote.PmacSerialInterface()
        obj.hostname = 'hostname'
        obj.port = 1234
        obj.isConnectionOpen = True
        actual_return = obj.connect()
        expected_return = "Socket is already open"
        self.assertEqual(actual_return, expected_return)

    @patch("serial.Serial")
    def test_port_in_use(self, mock_serial):
        mock_serial.side_effect = serial.serialutil.SerialException
        obj = dls_pmacremote.PmacSerialInterface()
        obj.hostname = 'hostname'
        obj.port = 1234
        actual_return = obj.connect()
        expected_return = "Port already in use!"
        self.assertEqual(actual_return, expected_return)

    @patch("dls_pmacremote.PmacSerialInterface._sendCommand")
    @patch("serial.Serial")
    def test_connect_io_error(self, mock_serial, mock_sendcmd):
        mock_sendcmd.side_effect = IOError
        obj = dls_pmacremote.PmacSerialInterface()
        obj.isConnectionOpen = False
        with self.assertRaises(IOError):
            obj.connect()
        assert obj.isConnectionOpen == False

    def test_disconnect_no_connection_open(self):
        obj = dls_pmacremote.PmacSerialInterface()
        obj.isConnectionOpen = False
        actual_return = obj.disconnect()
        assert actual_return == None

    @patch("serial.Serial")
    def test_disconnect_connection_open(self, mock_serial):
        obj = dls_pmacremote.PmacSerialInterface()
        obj.isConnectionOpen = True
        obj.serial = mock_serial.return_value
        obj.disconnect()
        assert obj.isConnectionOpen == False

    '''@patch("serial.Serial.read", return_value = b"response\x06")
    @patch("serial.Serial")
    def test_sendCommand(self, mock_serial, mock_read):
        obj = dls_pmacremote.PmacSerialInterface()
        obj.serial = mock_serial.return_value
        obj._sendCommand("cmd")'''

if __name__ == '__main__':
        unittest.main()
