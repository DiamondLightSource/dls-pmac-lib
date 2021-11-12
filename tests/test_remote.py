import unittest
from mock import patch, Mock
import sys
sys.path.append('/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib')
import dls_pmacremote
import paramiko
import socket
import serial
import types

class TestRemotePmacInterface(unittest.TestCase):

    def setUp(self):
        self.obj = dls_pmacremote.RemotePmacInterface()
        self.obj.verboseMode = False

    def test_setConnectionParams(self):
        self.obj.setConnectionParams()
        assert self.obj.hostname == "localhost"
        assert self.obj.port == None

    @patch("dls_pmacremote.RemotePmacInterface._sendCommand", return_value = "response")
    def test_send_command(self, mock_send_cmd):
        response, success = self.obj.sendCommand("test")
        assert response == "response"
        assert success == True

    @patch("dls_pmacremote.RemotePmacInterface._sendCommand")
    def test_send_command_null_error(self, mock_send_cmd):
        mock_send_cmd.side_effect = IOError
        response, success = self.obj.sendCommand("test")
        assert response == "I/O error during comm with PMAC: "
        assert success == False

    @patch("dls_pmacremote.RemotePmacInterface")
    def test_send_command_not_implemented(self, mock_sendcmd):
        mock_instance = Mock()
        mock_instance._sendCommand.side_effect = NotImplementedError
        mock_sendcmd.return_value = mock_instance
        with self.assertRaises(NotImplementedError):
            self.obj._sendCommand("command")

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_get_pmac_model_code(self, mock_send_cmd):
        mock_send_cmd.return_value = ("123456\r\x06", True)
        self.obj._pmacModelCode = None
        assert self.obj.getPmacModelCode() == 123456

    @patch("dls_pmacremote.RemotePmacInterface.getPmacModelCode")
    def test_get_pmac_model(self, mock_get_code):
        mock_get_code.return_value = 603382
        self.obj._pmacModelName = None
        assert self.obj.getPmacModel() == "Geo Brick (3U Turbo PMAC2)"

    @patch("dls_pmacremote.RemotePmacInterface.getPmacModelCode")
    def test_get_pmac_model_short_name(self, mock_get_code):
        mock_get_code.return_value = 603382
        self.obj._shortModelName = None
        assert self.obj.getShortModelName() == "Geobrick"

    @patch("dls_pmacremote.RemotePmacInterface.getIVars")
    def test_get_num_macro_station_axes(self, mock_get_ivars):
        mock_get_ivars.return_value = [1,2,3,4]
        assert self.obj._getNumberOfMacroStationAxes() == 32

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_send_series(self, mock_send_cmd):
        mock_send_cmd.return_value = ("repsonse",True)
        ret = self.obj.sendSeries(["cmd1","cmd2","cmd3"])
        assert isinstance(ret, types.GeneratorType)

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_disable_limits_not_enabled_disable_true(self, mock_send_cmd):
        mock_send_cmd.return_value = ("$820401\r\x06",True)
        cmd, retStr, status = self.obj.disableLimits(1,True)
        assert cmd == ""
        assert retStr == ""
        assert status == False
