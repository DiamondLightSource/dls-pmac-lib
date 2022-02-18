import types
import unittest

import dls_pmaclib.dls_pmacremote as dls_pmacremote
from mock import patch


class TestRemotePmacInterface(unittest.TestCase):
    def setUp(self):
        self.obj = dls_pmacremote.RemotePmacInterface()

    def test_init(self):
        assert self.obj.verboseMode is False
        assert self.obj.hostname == ""
        assert self.obj.port is None
        assert self.obj.parent is None
        assert self.obj.isConnectionOpen is False
        assert self.obj.timeout == 3.0
        assert self.obj._isModelGeobrick is None
        assert self.obj._pmacModelCode is None
        assert self.obj._pmacModelName is None
        assert self.obj._shortModelName is None
        assert self.obj._numAxes is None
        assert self.obj.baud_rate is None
        assert self.obj.comm_port is None
        assert self.obj.last_received_packet is None
        assert self.obj.last_comm_time is None
        assert self.obj.n_timeouts is None
        assert self.obj.serial is None

    def test_setConnectionParams(self):
        self.obj.setConnectionParams()
        assert self.obj.hostname == "localhost"
        assert self.obj.port is None

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface._sendCommand")
    def test_send_command(self, mock_send_cmd):
        mock_send_cmd.return_value = "response"
        response, success = self.obj.sendCommand("test")
        mock_send_cmd.assert_called_with("test", shouldWait=True, doubleTimeout=False)
        assert response == "response"
        assert success is True

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface._sendCommand")
    def test_send_command_null_error(self, mock_send_cmd):
        mock_send_cmd.side_effect = IOError
        response, success = self.obj.sendCommand("test")
        mock_send_cmd.assert_called_with("test", shouldWait=True, doubleTimeout=False)
        assert response == "I/O error during comm with PMAC: "
        assert success is False

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface._sendCommand")
    def test__send_command_not_implemented(self, mock_send_cmd):
        mock_send_cmd.side_effect = NotImplementedError
        not_implemented_str = (
            "This method must be implemented by one of the child classes"
        )
        with self.assertRaises(NotImplementedError):
            assert self.obj._sendCommand("command") == not_implemented_str
        mock_send_cmd.assert_called_with("command")

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_get_pmac_model_code(self, mock_send_cmd):
        mock_send_cmd.return_value = ("123456\r\x06", True)
        assert self.obj.getPmacModelCode() == 123456

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getPmacModelCode")
    def test_get_pmac_model(self, mock_get_code):
        mock_get_code.return_value = 603382
        assert self.obj.getPmacModel() == "Geo Brick (3U Turbo PMAC2)"

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getPmacModelCode")
    def test_get_pmac_model_short_name(self, mock_get_code):
        mock_get_code.return_value = 603382
        assert self.obj.getShortModelName() == "Geobrick"

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getPmacModelCode")
    def test_is_model_geobrick(self, mock_get_code):
        mock_get_code.return_value = 603382
        assert self.obj.isModelGeobrick() is True

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getIVars")
    def test_get_num_macro_station_axes(self, mock_get_ivars):
        mock_get_ivars.return_value = [1, 2, 3, 4]
        assert self.obj._getNumberOfMacroStationAxes() == 32

    @patch(
        "dls_pmaclib.dls_pmacremote.RemotePmacInterface._getNumberOfMacroStationAxes"
    )
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    def test_getNumberOfAxes(self, mock_geobrick, mock_axes):
        mock_geobrick.return_value = True
        mock_axes.return_value = 0
        assert self.obj.getNumberOfAxes() == 8

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getNumberOfAxes")
    def test_axis_in_range(self, mock_get_axes):
        mock_get_axes.return_value = 4
        assert self.obj.checkAxisIsInRange(2) is None
        assert mock_get_axes.called

    def test_axis_in_range_negative(self):
        with self.assertRaises(ValueError):
            assert self.obj.checkAxisIsInRange(-1) == "Asking for a negative axis"

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getNumberOfAxes")
    def test_axis_in_range_out_of_range(self, mock_get_axes):
        mock_get_axes.return_value = 4
        value_error_str = "Requested axis 6 but PMAC has only 4 axes"
        with self.assertRaises(ValueError):
            assert self.obj.checkAxisIsInRange(6) == value_error_str
        assert mock_get_axes.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getAxisMacroStationNumber_not_geobrick(
        self, mock_checkaxis, mock_isgeobrick
    ):
        mock_checkaxis.return_value = None
        mock_isgeobrick.return_value = False
        assert self.obj.getAxisMacroStationNumber(1) == 0
        assert mock_checkaxis.called
        assert mock_isgeobrick.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getAxisMacroStationNumber_is_geobrick(
        self, mock_checkaxis, mock_isgeobrick
    ):
        mock_checkaxis.return_value = None
        mock_isgeobrick.return_value = True
        assert self.obj.getAxisMacroStationNumber(9) == 0
        assert mock_checkaxis.called
        assert mock_isgeobrick.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getAxisMacroStationNumber_not_macro_ring(
        self, mock_checkaxis, mock_isgeobrick
    ):
        mock_checkaxis.return_value = None
        mock_isgeobrick.return_value = True
        value_error_str = "Axis 3 is not on the MACRO ring"
        with self.assertRaises(ValueError):
            assert self.obj.getAxisMacroStationNumber(3) == value_error_str
        assert mock_checkaxis.called
        assert mock_isgeobrick.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_isMacroStationAxis_not_geobrick(self, mock_checkaxis, mock_isgeobrick):
        mock_checkaxis.return_value = None
        mock_isgeobrick.return_value = False
        assert self.obj.isMacroStationAxis(1) is True
        assert mock_checkaxis.called
        assert mock_isgeobrick.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_isMacroStationAxis_false(self, mock_checkaxis, mock_isgeobrick):
        mock_checkaxis.return_value = None
        mock_isgeobrick.return_value = True
        assert self.obj.isMacroStationAxis(1) is False
        assert mock_checkaxis.called
        assert mock_isgeobrick.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isModelGeobrick")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_isMacroStationAxis_true(self, mock_checkaxis, mock_isgeobrick):
        mock_checkaxis.return_value = None
        mock_isgeobrick.return_value = True
        assert self.obj.isMacroStationAxis(10) is True
        assert mock_checkaxis.called
        assert mock_isgeobrick.called

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_getIVars(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response\rresponse\rresponse\rx06", True)
        ret = self.obj.getIVars(100, [1, 2, 3])
        mock_sendcmd.assert_called_with("i101 i102 i103 ")
        assert ret == ["response", "response", "response"]

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_setVar_successful(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        assert self.obj.setVar("var", 100) is None
        mock_sendcmd.assert_called_with("var=100")

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_setVar_not_successful(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", False)
        IOerror_str = "Cannot set variable: error communicating with PMAC"
        with self.assertRaises(IOError):
            assert self.obj.setVar("var", 100) == IOerror_str
        mock_sendcmd.assert_called_with("var=100")

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getIVars")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getAxisSetupIVars(self, mock_checkaxis, mock_getivars):
        mock_checkaxis.return_value = None
        mock_getivars.return_value = "ret"
        assert self.obj.getAxisSetupIVars(1, [1, 2, 3]) == "ret"
        mock_checkaxis.assert_called_with(1)
        mock_getivars.assert_called_with(100, [1, 2, 3])

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.setVar")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_setAxisSetupIVar(self, mock_checkaxis, mock_setvar):
        mock_checkaxis.return_value = None
        mock_setvar.return_value = None
        assert self.obj.setAxisSetupIVar(1, 1, 5) is None
        mock_checkaxis.assert_called_with(1)
        mock_setvar.assert_called_with("i101", 5)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getAxisMacroStationNumber")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getAxisMsIVars(self, mock_check, mock_get, mock_sendcmd):
        mock_check.return_value = None
        mock_get.return_value = 10
        mock_sendcmd.return_value = ("response\rresponse\rresponse\rx06", True)
        ret = self.obj.getAxisMsIVars(2, [100, 200, 300])
        mock_check.assert_called_with(2)
        mock_get.assert_called_with(2)
        mock_sendcmd.assert_called_with("ms10,i100 ms10,i200 ms10,i300 ")
        assert ret == ["response", "response", "response"]

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.setVar")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getAxisMacroStationNumber")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_setAxisMsIVar(self, mock_check, mock_get, mock_set):
        mock_check.return_value = None
        mock_get.return_value = 10
        mock_set.return_value = None
        assert self.obj.setAxisMsIVar(1, 100, 5) is None
        mock_check.assert_called_with(1)
        mock_get.assert_called_with(1)
        mock_set.assert_called_with("ms10,i100", 5)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.isMacroStationAxis")
    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.checkAxisIsInRange")
    def test_getOnboardAxisI7000PlusVarsBase(self, mock_check, mock_macro):
        mock_check.return_value = None
        mock_macro.return_value = False
        assert self.obj.getOnboardAxisI7000PlusVarsBase(4) == 7040
        mock_check.assert_called_with(4)
        mock_macro.assert_called_with(4)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.getIVars")
    @patch(
        "dls_pmaclib.dls_pmacremote.RemotePmacInterface.getOnboardAxisI7000PlusVarsBase"
    )
    def test_getOnboardAxisI7000PlusVars(self, mock_get, mock_getivars):
        mock_get.return_value = 100
        mock_getivars.return_value = "ret"
        assert self.obj.getOnboardAxisI7000PlusVars(1, [1, 2, 3]) == "ret"
        mock_get.assert_called_with(1)
        mock_getivars.assert_called_with(100, [1, 2, 3])

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.setVar")
    @patch(
        "dls_pmaclib.dls_pmacremote.RemotePmacInterface.getOnboardAxisI7000PlusVarsBase"
    )
    def test_setOnboardAxisI7000PlusIVar(self, mock_get, mock_setvar):
        mock_get.return_value = 100
        mock_setvar.return_value = None
        assert self.obj.setOnboardAxisI7000PlusIVar(1, 2, 5) is None
        mock_get.assert_called_with(1)
        mock_setvar.assert_called_with("i102", 5)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_send_series(self, mock_send_cmd):
        mock_send_cmd.return_value = ("response", True)
        ret = self.obj.sendSeries([(0, "cmd1"), (1, "cmd2")])
        assert isinstance(ret, types.GeneratorType)
        assert (next(ret)) == (True, 0, "cmd1", "response")
        assert (next(ret)) == (True, 1, "cmd2", "response")

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogInc_neg(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogInc(1, "neg", 100)
        mock_sendcmd.assert_called_with("#1J^-100")
        assert ret == ("#1J^-100", "response", True)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogInc_pos(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogInc(1, "pos", 100)
        mock_sendcmd.assert_called_with("#1J^100")
        assert ret == ("#1J^100", "response", True)

    def test_jogInc_err(self):
        ret = self.obj.jogInc(1, "err", 100)
        assert ret == ("Error, could not recognise direction: err", False)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogStop(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogStop(1)
        mock_sendcmd.assert_called_with("#1J/")
        assert ret == ("#1J/", "response", True)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogTo(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogTo(1, 1000)
        mock_sendcmd.assert_called_with("#1J=1000")
        assert ret == ("#1J=1000", "response", True)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogCont_neg(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogContinous(1, "neg")
        mock_sendcmd.assert_called_with("#1J-")
        assert ret == ("#1J-", "response", True)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_jogCont_pos(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.jogContinous(1, "pos")
        mock_sendcmd.assert_called_with("#1J+")
        assert ret == ("#1J+", "response", True)

    def test_jogCont_err(self):
        ret = self.obj.jogContinous(1, "err")
        assert ret == ("Error, could not recognise direction: err", False)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_home_cmd(self, mock_sendcmd):
        mock_sendcmd.return_value = ("response", True)
        ret = self.obj.homeCommand(1)
        mock_sendcmd.assert_called_with("#1HM")
        assert ret == ("#1HM", "response", True)

    @patch("dls_pmaclib.dls_pmacremote.RemotePmacInterface.sendCommand")
    def test_disable_limits_not_enabled_disable_true(self, mock_send_cmd):
        mock_send_cmd.return_value = ("$820401\r\x06", True)
        cmd, retStr, status = self.obj.disableLimits(1, True)
        mock_send_cmd.assert_called_with("i124")
        assert cmd == ""
        assert retStr == ""
        assert status is False
