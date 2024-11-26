import signal
import unittest
from unittest.mock import Mock, patch

import paramiko
from parameterized import parameterized

import dls_pmaclib.dls_pmacremote as dls_pmacremote


class TestSshInterface(unittest.TestCase):
    def setUp(self):
        self.obj = dls_pmacremote.PPmacSshInterface()
        self.obj.isConnectionOpen = False
        self.obj.hostname = "test"
        self.obj.port = 22

    def test_init(self):
        assert self.obj.client is None
        assert self.obj.num_recv_bytes == 8192

    def timeout_handler(self, signum, frame):
        raise TimeoutError("Function took too long to complete")

    @parameterized.expand(
        [
            ("test_wait_for_shell_ready", "@", b"root@123.45.67.89:/opt/ppmac"),
            ("test_wait_for_gpascii_ready", "ASCII", b"STDIN Open for ASCII Input"),
        ]
    )
    @patch(
        "time.sleep", return_value=None
    )  # Mock time.sleep to avoid delays in the test
    def test_wait_to_receive_string(
        self, name, string_to_wait_for, mock_response, mock_sleep
    ):
        # Mock the ssh client and its recv method response
        mock_client = Mock()
        mock_client.recv.return_value = mock_response

        # Set a timeout alarm for 2 seconds
        signal.signal(signal.SIGALRM, self.timeout_handler)
        signal.alarm(2)

        try:
            object = dls_pmacremote.PPmacSshInterface()
            object.wait_to_receive_string(mock_client, string_to_wait_for)
            # Cancel the alarm if the function returns in time
            signal.alarm(0)
        except TimeoutError:
            self.fail("Function took longer than 2 seconds to complete")

        # Assert that the recv method was called and the function returned
        mock_client.recv.assert_called()
        self.assertTrue(mock_client.recv.called)

    def test_connection_already_open(self):
        self.obj.isConnectionOpen = True
        assert self.obj.connect() == "Already connected"

    def test_hostname_not_set(self):
        self.obj.hostname = None
        assert self.obj.connect() == "ERROR: hostname not set"

    # when obj.connect() called, SSHClient object is initialised
    @patch("dls_pmaclib.dls_pmacremote.PPmacSshInterface.sendCommand")
    @patch("dls_pmaclib.dls_pmacremote.PPmacSshInterface.start_gpascii")
    @patch("paramiko.client.SSHClient.connect")
    @patch("paramiko.AutoAddPolicy")
    @patch("paramiko.client.SSHClient.set_missing_host_key_policy")
    def test_connects(
        self, mock_policy, mock_autoadd, mock_connect, mock_gpascii, mock_sendcmd
    ):
        mock_autoadd.return_value = None
        mock_policy.return_value = None
        mock_connect.return_value = None
        mock_sendcmd.return_value = ("response", True)
        assert self.obj.connect() is None
        assert mock_policy.called
        assert mock_autoadd.called
        mock_connect.assert_called_with(
            "test", 22, username="root", password="deltatau", timeout=3.0
        )
        assert mock_gpascii.called
        mock_sendcmd.assert_called_with("echo 7")
        assert self.obj.isConnectionOpen is True

    # when obj.connect() called, SSHClient object is initialised
    @patch("paramiko.client.SSHClient.connect")
    @patch("paramiko.AutoAddPolicy")
    @patch("paramiko.client.SSHClient.set_missing_host_key_policy")
    def test_wrong_username_password(self, mock_policy, mock_autoadd, mock_connect):
        mock_autoadd.return_value = None
        mock_policy.return_value = None
        mock_connect.side_effect = paramiko.ssh_exception.AuthenticationException
        ret = self.obj.connect(username="incorrect", password="incorrect")
        assert ret == "Invalid username or password"
        assert mock_policy.called
        assert mock_autoadd.called
        mock_connect.assert_called_with(
            "test", 22, username="incorrect", password="incorrect", timeout=3.0
        )
        assert self.obj.isConnectionOpen is False

    # when obj.connect() called, SSHClient object is initialised
    @patch("paramiko.client.SSHClient.connect")
    @patch("paramiko.AutoAddPolicy")
    @patch("paramiko.client.SSHClient.set_missing_host_key_policy")
    def test_connection_error(self, mock_policy, mock_autoadd, mock_connect):
        mock_autoadd.return_value = None
        mock_policy.return_value = None
        mock_connect.side_effect = Exception()
        ret = self.obj.connect()
        assert ret == "Cannot connect to test 22"
        assert mock_policy.called
        assert mock_autoadd.called
        mock_connect.assert_called_with(
            "test", 22, username="root", password="deltatau", timeout=3.0
        )
        assert self.obj.isConnectionOpen is False

    # when obj.connect() called, SSHClient object is initialised
    @patch("paramiko.client.SSHClient.connect")
    @patch("paramiko.AutoAddPolicy")
    @patch("paramiko.client.SSHClient.set_missing_host_key_policy")
    def test_connect_port_not_set(self, mock_policy, mock_autoadd, mock_connect):
        mock_autoadd.return_value = None
        mock_policy.return_value = None
        mock_connect.side_effect = Exception()
        self.obj.port = None
        ret = self.obj.connect()
        assert ret == "Cannot connect to test None"
        assert mock_policy.called
        assert mock_autoadd.called
        mock_connect.assert_called_with(
            "test", None, username="root", password="deltatau", timeout=3.0
        )
        assert self.obj.isConnectionOpen is False

    def test_disconnect_no_connection_open(self):
        assert self.obj.disconnect() is None

    def test_disconnect_connection_open(self):
        self.obj.client = Mock()
        self.obj.isConnectionOpen = True
        assert self.obj.disconnect() is None
        assert self.obj.isConnectionOpen is False
        assert self.obj.client.close.called

    @patch("dls_pmaclib.dls_pmacremote.PPmacSshInterface.getPmacModelCode")
    def test_get_pmac_model(self, mock_getcode):
        mock_getcode.return_value = 604020
        assert self.obj.getPmacModel() == "Power PMAC UMAC"
        assert mock_getcode.called

    def test_get_pmac_model_is_not_none(self):
        self.obj._pmacModelName = "name"
        assert self.obj.getPmacModel() == "name"

    @patch("dls_pmaclib.dls_pmacremote.PPmacSshInterface.getPmacModelCode")
    def test_get_pmac_model_unsupported(self, mock_get_model_code):
        mock_get_model_code.return_value = 0
        with self.assertRaises(ValueError):
            assert self.obj.getPmacModel() == "Unsupported PMAC model"
        assert self.obj._pmacModelName is None
        assert mock_get_model_code.called

    @patch("dls_pmaclib.dls_pmacremote.PPmacSshInterface.sendCommand")
    def test_get_pmac_model_code(self, mock_send_cmd):
        mock_send_cmd.return_value = ("123456", True)
        assert self.obj.getPmacModelCode() == 123456
        mock_send_cmd.assert_called_with("cid")

    @patch("dls_pmaclib.dls_pmacremote.PPmacSshInterface.sendCommand")
    def test_get_number_axes(self, mock_send_cmd):
        mock_send_cmd.return_value = ("5", True)
        assert self.obj.getNumberOfAxes() == 4
        mock_send_cmd.assert_called_with("Sys.MaxMotors")

    def test_sendCommand(self):
        self.obj.gpascii_client = Mock()
        attrs = {
            "send.return_value": 2,
            "recv_ready.return_value": True,
            "recv.return_value": b"\x06\r\n\x06\r\n",
        }
        self.obj.gpascii_client.configure_mock(**attrs)
        assert self.obj._sendCommand("command") == "\r\r"
        self.obj.gpascii_client.send.assert_called_with("command\r\n")
        assert self.obj.gpascii_client.recv_ready.called
        self.obj.gpascii_client.recv.assert_called_with(8192)

    def test_get_file(self):
        self.obj.client = Mock()
        attrs = {"open_sftp.return_value": Mock()}
        self.obj.client.configure_mock(**attrs)
        assert self.obj.getFile("remote", "local") is None
        assert self.obj.client.open_sftp.called
        self.obj.client.open_sftp().get.assert_called_with("remote", "local")
        assert self.obj.client.open_sftp().close.called

    def test_put_file(self):
        self.obj.client = Mock()
        attrs = {"open_sftp.return_value": Mock()}
        self.obj.client.configure_mock(**attrs)
        assert self.obj.putFile("local", "remote") is None
        assert self.obj.client.open_sftp.called
        self.obj.client.open_sftp().put.assert_called_with("local", "remote")
        assert self.obj.client.open_sftp().close.called

    def test_send_ssh_command(self):
        self.obj.client = Mock()
        attrs = {"exec_command.return_value": ("in", "out", "err")}
        self.obj.client.configure_mock(**attrs)
        assert self.obj.sendSshCommand("cmd") is None
        self.obj.client.exec_command.assert_called_with("cmd\n")
