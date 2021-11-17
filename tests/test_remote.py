import unittest
from mock import patch, Mock
import sys

sys.path.append("/home/dlscontrols/bem-osl/dls-pmac-lib/dls_pmaclib")
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

    @patch("dls_pmacremote.RemotePmacInterface._sendCommand", return_value="response")
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
        mock_get_ivars.return_value = [1, 2, 3, 4]
        assert self.obj._getNumberOfMacroStationAxes() == 32

    @patch("dls_pmacremote.RemotePmacInterface._getNumberOfMacroStationAxes")
    @patch("dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    def test_getNumberOfAxes(self, mock_geobrick, mock_axes):
        mock_geobrick.return_value = True
        mock_axes.return_value = 0
        self.obj._numAxes = None
        ret = self.obj.getNumberOfAxes()
        assert ret == 8

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    @patch("dls_pmacremote.RemotePmacInterface.getAxisMacroStationNumber")
    @patch("dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getAxisMsIVars(self, mock_check, mock_get, mock_sendcmd):
        mock_get.return_value = 10
        mock_sendcmd.return_value = ("response\rresponse\rresponse\rx06", True)
        ret = self.obj.getAxisMsIVars(2, [100, 200, 300])
        assert mock_check.called
        assert mock_get.called
        mock_sendcmd.assert_called_with("ms10,i100 ms10,i200 ms10,i300 ")
        assert ret == ["response", "response", "response"]

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_getIVars(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response\rresponse\rresponse\rx06", True)
        ret = self.obj.getIVars(100, [1, 2, 3])
        mock_sendcmd.assert_called_with("i101 i102 i103 ")
        assert ret == ["response", "response", "response"]

    @patch("dls_pmacremote.RemotePmacInterface.isMacroStationAxis")
    @patch("dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getIVars(self, mock_check, mock_macro):
        mock_macro.return_value = False
        ret = self.obj.getOnboardAxisI7000PlusVarsBase(4)
        assert ret == 7115

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_send_series(self, mock_send_cmd):
        mock_send_cmd.return_value = ("response", True)
        ret = self.obj.sendSeries([(0, "cmd1"), (1, "cmd2")])
        assert isinstance(ret, types.GeneratorType)
        assert (next(ret)) == (True, 0, "cmd1", "response")
        assert (next(ret)) == (True, 1, "cmd2", "response")

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogInc_neg(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogInc(1, "neg", 100)
        mock_sendcmd.assert_called_with("#1J^-100")
        assert ret == ("#1J^-100", "response", True)

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogInc_pos(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogInc(1, "pos", 100)
        mock_sendcmd.assert_called_with("#1J^100")
        assert ret == ("#1J^100", "response", True)

    def test_jogInc_err(self):
        ret = self.obj.jogInc(1, "err", 100)
        assert ret == ("Error, could not recognise direction: err", False)

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogCont_neg(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogContinous(1, "neg")
        mock_sendcmd.assert_called_with("#1J-")
        assert ret == ("#1J-", "response", True)

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogCont_pos(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogContinous(1, "pos")
        mock_sendcmd.assert_called_with("#1J+")
        assert ret == ("#1J+", "response", True)

    def test_jogCont_err(self):
        ret = self.obj.jogContinous(1, "err")
        assert ret == ("Error, could not recognise direction: err", False)

    @patch("dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_disable_limits_not_enabled_disable_true(self, mock_send_cmd):
        mock_send_cmd.return_value = ("$820401\r\x06", True)
        cmd, retStr, status = self.obj.disableLimits(1, True)
        assert cmd == ""
        assert retStr == ""
        assert status == False
