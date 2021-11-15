import unittest
from mock import patch, Mock
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
import dls_pmacremote
import paramiko
import types

class TestSshInterface(unittest.TestCase):

    def setUp(self):
        self.obj = dls_pmacremote.PPmacSshInterface()
        self.obj.isConnectionOpen = False
        self.obj.hostname = 'test'
        self.obj.port = 22

    @patch("dls_pmacremote.PPmacSshInterface.client.invoke_shell")
    @patch("dls_pmacremote.PPmacSshInterface.client")
    def test_start_gpascii(self, mock_client, mock_gpascii):
        mock_instance = Mock()
        mock_instance.send.return_value = None
        mock_instance.recv.return_value = "ASCII".encode()
        mock_gpascii.return_value = mock_instance
        ret = self.obj.start_gpascii()
        assert ret == None
        assert self.obj.gpascii_issued == True

    def test_connection_already_open(self):
        self.obj.isConnectionOpen = True
        assert self.obj.connect() == "Already connected"

    def test_hostname_not_set(self):
        self.obj.hostname = None
        assert self.obj.connect() == "ERROR: hostname not set"

    # when obj.connect() called, SSHClient object is initialised 
    @patch("dls_pmacremote.PPmacSshInterface.sendCommand", return_value = (None,None))
    @patch("dls_pmacremote.PPmacSshInterface.start_gpascii")
    @patch("paramiko.client.SSHClient.connect")
    def test_connects(self, mock_connect, mock_gpascii, mock_sendcmd):
        self.obj.connect()
        assert mock_connect.called
        assert mock_gpascii.called
        assert mock_sendcmd.called
        assert self.obj.isConnectionOpen == True

    @patch("paramiko.client.SSHClient.connect")
    def test_wrong_username_password(self, mock_connect):
        mock_connect.side_effect = paramiko.ssh_exception.AuthenticationException
        ret = self.obj.connect(username="incorrect", password="incorrect")
        assert ret == "Invalid username or password"

    @patch("paramiko.client.SSHClient.connect")
    def test_connection_error(self, mock_connect):
        mock_connect.side_effect = Exception()
        ret = self.obj.connect(username="incorrect")
        assert ret == "Cannot connect to test 22"

    @patch("paramiko.client.SSHClient.connect")
    def test_port_not_set(self, mock_connect):
        mock_connect.side_effect = Exception()
        self.obj.port = None
        ret = self.obj.connect()
        assert ret == "Cannot connect to test None"

    def test_disconnect_no_connection_open(self):
        ret = self.obj.disconnect()
        assert ret == None

    @patch("paramiko.client.SSHClient")
    def test_disconnect_connection_open(self, mock_client):
        self.obj.isConnectionOpen = True
        self.obj.client = mock_client.return_value
        self.obj.disconnect()
        assert self.obj.isConnectionOpen == False

    @patch("dls_pmacremote.PPmacSshInterface.sendCommand")
    def test_get_pmac_model_code(self, mock_send_cmd):
        mock_send_cmd.return_value = ("123456", True)
        self.obj._pmacModelCode = None
        assert self.obj.getPmacModelCode() == 123456

    def test_sendCommand(self):
        self.obj.gpascii_client = Mock()
        attrs = {
        "send.return_value" : "n",
        "recv_ready.return_value" : True,
        "recv.return_value" : "\x06\r\n\x06\r\n".encode()}
        self.obj.gpascii_client.configure_mock(**attrs)
        ret = self.obj._sendCommand("command")
        assert ret == None

    #@unittest.skip("need to mock sftp.get")
    @patch("dls_pmacremote.PPmacSshInterface.client.open_sftp")
    @patch("dls_pmacremote.PPmacSshInterface.client")
    def test_get_file(self, mock_client, mock_open):
        ret = self.obj.getFile("remote","local")
        assert ret == None
        assert mock_open.called

    #@unittest.skip("need to mock sftp.put")
    @patch("dls_pmacremote.PPmacSshInterface.client.open_sftp")
    @patch("dls_pmacremote.PPmacSshInterface.client")
    def test_put_file(self, mock_client, mock_open):
        ret = self.obj.putFile("local","remote")
        assert ret == None
        assert mock_open.called

    def test_send_ssh_command(self):
        self.obj.client = Mock()
        attrs = {"exec_command.return_value" : ("in","out","err")}
        self.obj.client.configure_mock(**attrs)
        ret = self.obj.sendSshCommand("cmd")
        self.obj.client.exec_command.assert_called_with("cmd\n")
        assert ret == None

    def test_get_pmac_model(self):
        self.obj._pmacModelName = 'name'
        ret = self.obj.getPmacModel()
        assert ret == 'name'

    @patch("dls_pmacremote.PPmacSshInterface.getPmacModelCode", return_value=604020)
    def test_get_pmac_model_is_none(self, mock_get_pmac_model_name):
        self.obj._pmacModelName = None
        ret = self.obj.getPmacModel()
        assert ret == "Power PMAC UMAC"

    @patch("dls_pmacremote.PPmacSshInterface.getPmacModelCode", return_value=0)
    def test_get_pmac_model_unsupported(self, mock_get_model_code):
        self.obj._pmacModelName = None
        with self.assertRaises(ValueError):
            self.obj.getPmacModel()
        assert self.obj._pmacModelName == None

    @patch("dls_pmacremote.PPmacSshInterface.sendCommand", return_value = (5,True))
    def test_get_number_axes(self, mock_sendcmd):
        ret = self.obj.getNumberOfAxes()
        assert ret == 4
