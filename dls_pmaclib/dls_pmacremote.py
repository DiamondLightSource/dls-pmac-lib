import errno
import re
import socket
import struct
import sys
import telnetlib
import threading
import time
from logging import getLogger

import paramiko
import serial
from paramiko import SSHClient

log = getLogger("dls_pmaclib")


class IOPmacSentNullError(IOError):
    pass


CHAR_ACK = "\x06"
CHAR_RETURN = "\x0D"
CHAR_NULL = "\x00"
CHAR_BELL = "\x07"
VALID_ENDS = (CHAR_ACK, CHAR_RETURN)


# noinspection PyPep8Naming
class RemotePmacInterface:
    """This class provides a common interface to a remote PMAC. It provides
    methods
           to connect to the PMAC (e.g. via a Telnet terminal server
       session or Ethernet), to disconnect, and to issue commands. It provides
           methods for some basic axis commands (e.g. move/jog axis etc.).
           It is
           a base class that should not be instantiated directly."""

    PMAC_errors = {
        "ERR001": "Command not allowed during program execution",
        "ERR002": "Password error",
        "ERR003": "Data error or unrecognized command",
        "ERR004": "Illegal character: bad value (>127 ASCII) or serial "
        "parity/framing error",
        "ERR005": "Command not allowed unless buffer is open",
        "ERR006": "No room in buffer for command",
        "ERR007": "Buffer already in use",
        "ERR008": "MACRO auxiliary communications error",
        "ERR009": "Program structural error",
        "ERR010": "Both overtravel limits set for a motor in the C.S.",
        "ERR011": "Previous move not completed",
        "ERR012": "A motor in the coordinate system is open-loop",
        "ERR013": "A motor in the coordinate system is not activated",
        "ERR014": "No motors in the coordinate system",
        "ERR015": "Not pointing to valid program buffer",
        "ERR016": "Running improperly structured program",
        "ERR017": "Trying to resume after H or Q with motors out of stopped "
        "position",
        "ERR018": "Attempt to perform phase reference during move, "
        "move during phase reference., or enabling with phase clock "
        "error.",
        "ERR019": "Illegal position-change command while moves stored in " "CCBUFFER",
    }

    def __init__(self, parent=None, verbose=False, numAxes=None, timeout=3.0):
        # Basic connection settings
        self.verboseMode = verbose
        self.hostname = ""
        self.port = None
        self.parent = parent

        # Access-to-the-connection semaphore. Use this to lock/unlock I/O
        # access to the connection (whatever type it is) in child classes.
        self.semaphore = threading.Semaphore()

        self.isConnectionOpen = False
        self.timeout = timeout

        # Use the getter self.isModelGeobrick() to access this. The value is
        # None if uninitialised.
        self._isModelGeobrick = None

        # These also need to be cached, as dls_pmaclib repeatedly polls
        # these values in the GUI.
        self._pmacModelCode = None
        self._pmacModelName = None
        self._shortModelName = None

        # Use the getter self.getNumberOfAxes() to access this. The value is
        # None if uninitialised.
        if numAxes is not None:
            self._numAxes = int(numAxes)
        else:
            self._numAxes = None

        self.MACRO_STATION_LOOKUP_TABLE = [
            0,
            1,
            4,
            5,
            8,
            9,
            12,
            13,
            16,
            17,
            20,
            21,
            24,
            25,
            28,
            29,
            32,
            33,
            36,
            37,
            40,
            41,
            44,
            45,
            48,
            49,
            52,
            53,
            56,
            57,
            60,
            61,
            64,
            65,
        ]
        self.baud_rate = None
        self.comm_port = None

        self.last_received_packet = None
        self.last_comm_time = None
        self.n_timeouts = None
        self.serial = None

    def setConnectionParams(self, host="localhost", port=None):
        self.hostname = str(host)
        if port:
            self.port = int(str(port))
        else:
            self.port = None

    # Connect to the host
    # Returns None if success. Error string if no connection parameters are
    # set or if failure.
    def connect(self, updatesReadyEvent=None):
        raise NotImplementedError("This method must be implemented in child classes")

    # disconnect from the host
    def disconnect(self):
        raise NotImplementedError("This method must be implemented in child classes")

    def sendCommand(self, command, shouldWait=True):
        """
        Send a single command to the controller and block until a response from
        the controller.
        This is a return-format wrapper for the _sendCommand() method, written
        as the existing code uses this
        form of sendCommand() a lot.
        Arguments: * command (str): is the command to be sent
                    * shouldWait (bool, optional, default True): whether to
                    wait
                    on the semaphore.
                      This should normally be left default. If we have acquired
                      the semaphore manually,
                      then specify shouldWait = False (and don't forget to
                      release
                      the semaphore eventually).
        Returns: A tuple (response, wasSuccessful), where:
                  * wasSuccessful (bool): is True unless there was an I/O
                  problem
                  during comm with the PMAC
                                          or the response does not have
                                          recognised
                                          terminators.
                                          Note that PMAC may still return an
                                          "ERRxxx" code; this function will
                                          still
                                          consider that a successful
                                          transmission.
                  * response (str): is either a string returned by the PMAC (on
                  success), or an error message (on failure)
        """
        # Submit the command to the low level function _sendCommand().
        # If I/O with the PMAC fails, return as a failure case.
        command = str(command)
        doubleTimeout = self.commandNeedsDoubleTimeout(command)
        (success, failure) = (True, False)
        try:
            response = self._sendCommand(
                command, shouldWait=shouldWait, doubleTimeout=doubleTimeout
            )
        except IOPmacSentNullError as e:
            # On the Ethernet interface the SAVE command responds
            # with '\x00' if it has changes to write, so in this
            # case we suppress the error on the SAVE command
            # itself, but not on any subsequent commands so as not
            # to mask a genuine problem.
            if doubleTimeout:
                if self.verboseMode:
                    log.warning(
                        "The PMAC returned a NULL character, probably due to "
                        "sending a SAVE command - command was %r" % command
                    )
                response = ""
            else:
                return "I/O error during comm with PMAC: %s" % str(e), failure
        except IOError as e:
            return "I/O error during comm with PMAC: %s" % str(e), failure
        return response, success

    # Send a single command to the controller and block until a response from
    # the controller.
    # This is the actual method that does the I/O with the remote PMAC,
    # and needs to be overridden in a child class;
    # each read/write cycle should be implemented to block.
    # Returns: a string with PMAC's response to the command.
    # Throws: an IOError if any I/O-related error occured.
    def _sendCommand(self, command, shouldWait=True, doubleTimeout=False):
        raise NotImplementedError(
            "This method must be implemented by one of the child classes"
        )

    # Return a number designating which PMAC model this is, or Exception on
    # error.
    def getPmacModelCode(self):
        # Ask for pmac model, returns an integer
        if self._pmacModelCode is None:
            (retStr, wasSuccessful) = self.sendCommand("cid")

            if not wasSuccessful:
                raise IOError("Error talking to PMAC")

            mo = re.compile(r"^(\d+)\r\x06$").match(retStr)
            if not mo:
                raise ValueError("Received malformed input from PMAC (%r)" % retStr)

            self._pmacModelCode = int(mo.group(1))

        return self._pmacModelCode

    # Return a string designating which PMAC model this is, or None on error
    def getPmacModel(self):
        # Return a model designation based on model code
        if self._pmacModelName is None:
            modelNamesByCode = {
                602404: "Turbo PMAC2 Clipper",
                602413: "Turbo PMAC2-VME",
                603382: "Geo Brick (3U Turbo PMAC2)",
            }

            modelCode = self.getPmacModelCode()
            try:
                self._pmacModelName = modelNamesByCode[modelCode]
            except KeyError:
                raise ValueError("Unsupported PMAC model")

        return self._pmacModelName

    def getShortModelName(self):
        # Return a short model name based on model code
        if self._shortModelName is None:
            shortModelNamesByCode = {
                602404: "Clipper",
                602413: "Pmac",
                603382: "Geobrick",
            }

            modelCode = self.getPmacModelCode()
            try:
                self._shortModelName = shortModelNamesByCode[modelCode]
            except KeyError:
                self._shortModelName = "Pmac"

        return self._shortModelName

    def isModelGeobrick(self):
        # Used to handle functionality specific to the Geobrick.
        # As a clipper board is based on the Geobrick, it is included here.
        if self._isModelGeobrick is None:
            # If self._isModelGeobrick is not initialised, do so now
            geobrickModelCodes = [602404, 603382]
            self._isModelGeobrick = self.getPmacModelCode() in geobrickModelCodes
        return self._isModelGeobrick

    # Get the number of macro stations available. This is given by number of
    # Macro ICs available. One MACRO IC can control up to 8 axes,
    # so the number returned is a multiple of 8. The availability of MACRO
    # ICs is determined by querying I20..23 (read-only variables).
    # The first MACRO IC is available if I20 (MACRO IC base address) is
    # non-zero.
    # The second, third, and fourth MACRO IC are similarly addressed by I21,
    # I22, I23.
    def _getNumberOfMacroStationAxes(self):
        macroIcAddresses = self.getIVars(0, [20, 21, 22, 23])  # access I20..23
        if self.verboseMode:
            log.info(
                "Got MACRO IC station base addresses: %s ($0 means not "
                "present)" % str(macroIcAddresses)
            )
        controllableAxesCount = 0
        for i in range(4):
            if macroIcAddresses[i] != "$0":
                controllableAxesCount += 8
        return controllableAxesCount

    # Get the total number of axes available
    def getNumberOfAxes(self):
        if self._numAxes is None:
            if self.isModelGeobrick():
                self._numAxes = 8 + self._getNumberOfMacroStationAxes()
            else:
                self._numAxes = self._getNumberOfMacroStationAxes()
        if self.verboseMode:
            log.info("Total number of axes is %d." % self._numAxes)
        return self._numAxes

    def checkAxisIsInRange(self, axis):
        if axis < 0:
            raise ValueError("Asking for a negative axis")
        if axis > self.getNumberOfAxes():
            raise ValueError(
                "Requested axis %d but PMAC has only %d axes"
                % (axis, self.getNumberOfAxes())
            )

    # Returns: Macro station number
    # Raises: ValueError if asking for non-existent axis, or not a MACRO ring
    # axis
    def getAxisMacroStationNumber(self, axis, macroAxisStartIndex=0):
        self.checkAxisIsInRange(axis)
        if not self.isModelGeobrick():
            return self.MACRO_STATION_LOOKUP_TABLE[axis - 1]
        else:
            if axis <= 8:
                raise ValueError("Axis %d is not on the MACRO ring" % axis)
            else:
                return (
                    self.MACRO_STATION_LOOKUP_TABLE[(axis - 8) - 1]
                    + macroAxisStartIndex
                )

    # Return True if this is a macro station axis, False if it is an
    # on-board-PMAC axis
    def isMacroStationAxis(self, axis):
        self.checkAxisIsInRange(axis)
        if not self.isModelGeobrick():
            return True
        else:
            return axis > 8

    # Get a list of values of Ixxxx variables, where xxxx = base + offset (
    # for each offset).
    def getIVars(self, base, offsets):
        iVars = map(lambda x: base + x, offsets)
        cmd = ""
        for iVar in iVars:
            cmd += "i%d " % iVar
        (retStr, status) = self.sendCommand(cmd)
        if status:
            return retStr.split("\r")[:-1]
        else:
            raise IOError("Cannot retrieve variable: error communicating with PMAC")

    def setVar(self, varName, value):
        (returnStr, wasSuccessful) = self.sendCommand("%s=%s" % (varName, str(value)))
        if not wasSuccessful:
            raise IOError("Cannot set variable: error communicating with PMAC")

    # Get a list of values of the "Setup I-variables" for a particular axis.
    # The "Setup I-variables" (thus named in the PMAC Software Reference
    # Manual) are the ones in the Ixxyy range, where xx = axis number,
    # yy = offset.
    # E.g. I one wants variables Ixx30, Ixx31 and Ixx32 for axis 14,
    # the should call self.getAxisISetupVars(14, [30,31,32]).
    def getAxisSetupIVars(self, axis, offsets):
        self.checkAxisIsInRange(axis)
        base = 100 * axis
        return self.getIVars(base, offsets)

    def setAxisSetupIVar(self, axis, offset, value):
        self.checkAxisIsInRange(axis)
        iVar = 100 * axis + offset
        self.setVar("i%d" % iVar, value)

    # Get macro station I-variables for a particular axis (or None on failure)
    def getAxisMsIVars(self, axis, msIVars, macroAxisStart=0):
        self.checkAxisIsInRange(axis)
        macroStationNo = self.getAxisMacroStationNumber(axis, macroAxisStart)
        cmd = ""
        for msIVar in msIVars:
            cmd += "ms%d,i%d " % (macroStationNo, msIVar)
        (retStr, status) = self.sendCommand(cmd)
        if status:
            return retStr.split("\r")[:-1]
        else:
            raise IOError("Cannot retrieve variable: error communicating with PMAC")

    def setAxisMsIVar(self, axis, iVar, value):
        self.checkAxisIsInRange(axis)
        macroStationNo = self.getAxisMacroStationNumber(axis)
        self.setVar("ms%d,i%d" % (macroStationNo, iVar), value)

    # Calculate the base I-variable number in the I70mn (say, "I7000+") range
    # for an onboard Geobrick axis.
    # For axes 1, 2, ... the bases are 7000, 7010, 7020, 7030, 7100, 7110,
    # 7120, 7130.
    def getOnboardAxisI7000PlusVarsBase(self, axis):
        # If not a Geobrick axis, raise an exception
        self.checkAxisIsInRange(axis)
        if self.isMacroStationAxis(axis):
            raise ValueError("Axis %d is not an onboard axis" % axis)

        # Calculate the base
        m = (axis - 1) // 4  # m in 0..9
        n = (axis - 1) % 4 + 1  # n in 1..4
        base = 7000 + m * 100 + n * 10
        return base

    def getOnboardAxisI7000PlusVars(self, axis, offsets):
        iVarsBase = self.getOnboardAxisI7000PlusVarsBase(axis)
        return self.getIVars(iVarsBase, offsets)

    def setOnboardAxisI7000PlusIVar(self, axis, offset, value):
        base = self.getOnboardAxisI7000PlusVarsBase(axis)
        iVar = base + offset
        self.setVar("i%d" % iVar, value)

    # function that sends out a whole list of commands to the pmac
    # (like from a file...). The function waits for a response from each command
    # and registers any errors returned.
    # After a command has been sent and a response received, the function
    # will post an event
    # to update the progress dialog in the main (GUI) thread.
    # cmdLst is a list of tuples: (lineNumber, command)
    # where command is the command from the file and lineNumber
    # is the line number from the original file.
    def sendSeries(self, cmdLst):
        errRegExp = re.compile(r"ERR\d{3}")

        # Acquire the semaphore controlling access to the connection
        self.semaphore.acquire()
        if self.verboseMode:
            log.debug("\n\n\n\nGot the semaphore!\n\n\n\n")

        for i, cmd in enumerate(cmdLst):
            # Send one line from to the controller.
            # Because we have acquired the semaphore already, we do not wait
            # for it again.
            (lineNumber, command) = cmd
            (pmacResponseStr, wasSuccessful) = self.sendCommand(
                command, shouldWait=False
            )
            # Check if PMAC returns an error as a response; if so, append the
            # error message to the error list
            if not wasSuccessful or errRegExp.findall(pmacResponseStr):
                wasSuccessful = False

            # yield control back
            try:
                yield (wasSuccessful, lineNumber, command, pmacResponseStr)
            except GeneratorExit:
                # user cancelled operation
                self.semaphore.release()
                if self.verboseMode:
                    log.debug(
                        "\n\n\n\nReleased the semaphore because of "
                        "cancellation!\n\n\n\n"
                    )
                return

        # Release the semaphore controlling access to the connection
        self.semaphore.release()
        if self.verboseMode:
            log.debug("\n\n\n\nReleased the semaphore!\n\n\n\n")

    # Controls whether to wait for double the normal timeout for this
    # message. Currently only used for the SAVE command.
    @staticmethod
    def commandNeedsDoubleTimeout(command):
        return "SAVE" in command.upper()

    # Jog incrementally
    # \motor the motor number to jog.
    # \direction string either "pos" or "neg"
    # \distance in counts
    def jogInc(self, motor, direction, distance):
        if direction == "neg":
            cmd = "#" + str(motor) + "J^-" + str(distance)
        elif direction == "pos":
            cmd = "#" + str(motor) + "J^" + str(distance)
        else:
            return "Error, could not recognise direction: " + str(direction), False

        (retStr, retStatus) = self.sendCommand(cmd)
        return cmd, retStr, retStatus

    def jogStop(self, motor):
        cmd = "#" + str(motor) + "J/"
        (retStr, retStatus) = self.sendCommand(cmd)
        return cmd, retStr, retStatus

    def jogTo(self, motor, new_position):
        cmd = "#" + str(motor) + "J=" + str(new_position)
        (retStr, retStatus) = self.sendCommand(cmd)
        return cmd, retStr, retStatus

    def jogContinous(self, motor, direction):
        if direction == "neg":
            cmd = "#" + str(motor) + "J-"
        elif direction == "pos":
            cmd = "#" + str(motor) + "J+"
        else:
            return "Error, could not recognise direction: " + str(direction), False

        (retStr, retStatus) = self.sendCommand(cmd)
        return cmd, retStr, retStatus

    def homeCommand(self, motor):
        cmd = "#" + str(motor) + "HM"
        (retStr, retStatus) = self.sendCommand(cmd)
        return cmd, retStr, retStatus

    def disableLimits(self, motor, disable):
        motor = str(motor)
        (retStr, status) = self.sendCommand("i" + motor + "24")
        if not status:
            return 1

        log.debug(retStr, status)
        initialLimits = int(retStr.strip("$\r\x06"), 16)
        currentlyEnabled = bool(not (initialLimits & 0x20000))

        if currentlyEnabled and disable:
            # Disable limits
            limitSetting = initialLimits | 0x20000
        elif (not currentlyEnabled) and (not disable):
            # enable limits
            limitSetting = initialLimits ^ 0x20000
        else:
            return "", "", False
        cmd = "i" + motor + "24=" + hex(limitSetting).replace("0x", "$")
        (retStr, status) = self.sendCommand(cmd)
        return cmd, retStr, status

    def testSendCommand(self):
        (s, code) = self.sendCommand("i20")
        log.info("i20: %r" % s)
        (s, code) = self.sendCommand("nonsense")
        log.info("nonsense: %r" % s)
        (s, code) = self.sendCommand("i20..23")
        log.info("i20..23: %r" % s)

    # ---------------------------------------------------------- Tests
    # ----------------------------------------------------------
    # A very basic test framework. Prints out test results onto standard output.
    # Run pmac.runTests() on a newly created pmac = PmacRemoteInterface(...)
    # object, which is already successfully connect()-ed.

    def testGetAxisMacroStationNumber(self):
        for i in range(1, 33):
            try:
                log.info(
                    "pmac.getAxisMacroStationNumber(%d) returns %s."
                    % (i, repr(self.getAxisMacroStationNumber(i)))
                )
            except Exception:
                log.debug("pmac.getAxisMacroStationNumber(%d)", i, exc_info=True)

    def testIsMacroStationAxis(self):
        for i in range(1, 33):
            try:
                log.info(
                    "pmac.isMacroStationAxis(%d) returns %s."
                    % (i, repr(self.isMacroStationAxis(i)))
                )
            except Exception:
                log.debug("pmac.isMacroStationAxis(%d)", i, exc_info=True)

    def runTests(self):
        log.info("______________________________________")
        self.testSendCommand()
        log.info("pmac.isModelGeobrick() returns %s", str(self.isModelGeobrick()))
        self.getNumberOfAxes()
        self.testIsMacroStationAxis()
        self.testGetAxisMacroStationNumber()


class PPmacSshInterface(RemotePmacInterface):

    client = None
    # Number of bytes to receive from communication channel
    num_recv_bytes = 8192

    def start_gpascii(self):
        # print("Starting gpascii")
        # Have to create a 'special shell' to invoke gpascii
        self.gpascii_client = self.client.invoke_shell(term="vt100")
        self.gpascii_client.send("gpascii -2\r\n")

        # Have to wait a few seconds to make sure the gpascii command has been issued
        # and we are 'in' to the ppmac. Wait from message 'STDIN Open for ASCII Input'
        self.gpascii_issued = False
        while not self.gpascii_issued:
            # Decode response
            time.sleep(0.1)
            response = self.gpascii_client.recv(2048)
            response = response.decode()
            if "ASCII" in response:
                self.gpascii_issued = True

        # print(" ... done")

    def connect(
        self, updatesReadyEvent=None, username="root", password="deltatau", timeout=3.0
    ):

        # Sanity checks
        if self.isConnectionOpen:
            return "Already connected"
        if self.hostname in (None, ""):
            return "ERROR: hostname not set"

        # Create SSH client
        self.client = SSHClient()
        # self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to IP address with username and password
        try:
            self.client.connect(
                self.hostname,
                self.port,
                username=username,
                password=password,
                timeout=timeout,
            )
        except paramiko.ssh_exception.AuthenticationException:
            return "Invalid username or password"
        except Exception:
            return "Cannot connect to " + self.hostname + " " + str(self.port)

        self.start_gpascii()

        # Format responses
        (retStr, wasSuccessful) = self.sendCommand("echo 7")

        self.isConnectionOpen = True

    def disconnect(self):
        if self.isConnectionOpen:
            self.semaphore.acquire()
            # print("Closing connection to '" + self.hostname + "'")
            self.client.close()
            self.semaphore.release()
            self.isConnectionOpen = False
            if self.verboseMode:
                log.warning("Disconnected from " + self.hostname)

    # Return a string designating which PMAC model this is, or None on error
    def getPmacModel(self):
        # Return a model designation based on model code
        if self._pmacModelName is None:
            modelNamesByCode = {604020: "Power PMAC UMAC"}

            modelCode = self.getPmacModelCode()
            try:
                self._pmacModelName = modelNamesByCode[modelCode]
            except KeyError:
                raise ValueError("Unsupported Power PMAC model")

        return self._pmacModelName

    # Return a number designating which PMAC model this is, or Exception on
    # error.
    def getPmacModelCode(self):
        # Ask for pmac model, returns an integer
        if self._pmacModelCode is None:
            (retStr, wasSuccessful) = self.sendCommand("cid")

            if not wasSuccessful:
                raise IOError("Error talking to Power PMAC")

            # mo = re.compile(r"^(\d+)\r\x06$").match(retStr)
            # if not mo:
            #    raise ValueError("Received malformed input from PMAC (%r)" % retStr)

            self._pmacModelCode = int(retStr)
            # self._pmacModelCode = int(mo.group(1))

            return self._pmacModelCode

    # Get the total number of axes available
    def getNumberOfAxes(self):
        (retStr, wasSuccessful) = self.sendCommand("Sys.MaxMotors")
        numMotors = int(retStr) - 1
        if self.verboseMode:
            log.info("Total number of motors is %d." % numMotors)
        return numMotors

    def _sendCommand(self, command, shouldWait=True, doubleTimeout=False):
        try:
            if shouldWait:
                self.semaphore.acquire()

            # print("Sending command: " + command)

            # Send a command
            stringToSend = command + "\r\n"
            try:
                n = self.gpascii_client.send(stringToSend)
                # Wait until we receive a response
                while not self.gpascii_client.recv_ready():
                    time.sleep(0.001)

                responseBytes = self.gpascii_client.recv(self.num_recv_bytes)

                # Decode
                response = responseBytes.decode()
                # Keep emptying the buffer until we find the ACK character,
                # signalling the end of the PPMAC's response
                startPos = 0
                while "\x06\r\n\x06\r\n" not in response[startPos:]:
                    responseBytes = self.gpascii_client.recv(self.num_recv_bytes)
                    response_ = (
                        responseBytes.decode()
                    )  # length of string depends on encoding
                    response += response_
                    startPos += len(response_)

                response = response[(n - 2) :]
                response = response.replace("\r\n\r\n", "")
                response = response.replace("\r\n", "\r")
                response = response.replace("\x06", "")
                response = response.replace("\r\r\r", "\r")
                return response
            except Exception:
                return None
        finally:
            if shouldWait:
                self.semaphore.release()

    # Copy remote file to local host
    def getFile(self, remotePath, localPath, shouldWait=True):
        try:
            if shouldWait:
                self.semaphore.acquire()

            try:
                sftp = self.client.open_sftp()
                sftp.get(remotePath, localPath)
                sftp.close()

            except Exception:
                print("Unable to get '%s' from remote host" % remotePath)

        finally:
            if shouldWait:
                self.semaphore.release()

    # Copy local file to remote host
    def putFile(self, localPath, remotePath, shouldWait=True):
        try:
            if shouldWait:
                self.semaphore.acquire()

            try:
                sftp = self.client.open_sftp()
                sftp.put(localPath, remotePath)
                sftp.close()

            except Exception:
                print("Unable to copy '%s' to remote host" % localPath)

        finally:
            if shouldWait:
                self.semaphore.release()

    # Send a command via ssh (not gpascii)
    def sendSshCommand(self, cmd, shouldWait=True):

        try:
            if shouldWait:
                self.semaphore.acquire()

            cmd += "\n"
            try:
                ssh_stdin, ssh_stdout, ssh_stderr = self.client.exec_command(cmd)

            except Exception:
                print("Unable to send command: '%s' via ssh" % cmd)

        finally:
            if shouldWait:
                self.semaphore.release()


# noinspection PyPep8Naming
class PmacEthernetInterface(RemotePmacInterface):
    """Allows connection to a PMAC over an Ethernet interface."""

    sock = None

    # Attempts to open a connection to a remote PMAC.
    # Returns None on success, or an error message string on failure.
    def connect(self, updatesReadyEvent=None):

        # Sanity checks
        if self.isConnectionOpen:
            return "Socket is already open"
        if self.hostname in (None, "") or self.port in (None, 0):
            return "ERROR: hostname or port number not set"

        # Create a new socket instance
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.sock.setblocking(1) # N.B.: line is pointless because the next
        # one overrides it
        self.sock.settimeout(self.timeout)

        # Attempt to establish a connection to the remote host
        try:
            if self.verboseMode:
                log.warning(
                    'Connecting a socket to host "%s" using port %d',
                    self.hostname,
                    self.port,
                )
            self.sock.connect((self.hostname, self.port))
            if self.verboseMode:
                log.warning(
                    'Connected to host "%s" on port %d' % (self.hostname, self.port)
                )
        except socket.gaierror:
            return "ERROR: unknown host"
        except Exception:
            return "ERROR: connection refused by host"

        self.isConnectionOpen = True

        # Check that the we are connected to a pmac by issuing the "ver"
        # command -- expecting the 1.922 in return.
        # If we don't get the right response, then disconnect automatically
        try:
            response = self._sendCommand("i6=1 i3=2 ver")
            if self.verboseMode:
                log.info("\tDevice responding." + response)
        except IOError:
            self.disconnect()
            return 'Device failed to respond to a "ver" command'
        if not re.match(r"^\d+\.\d+\s*\r\x06$", response):
            # if the response is not of the form "1.945  \r\x06" then we're
            # not talking to a PMAC!
            # log.error(response)
            self.disconnect()
            return 'Device did not respond correctly to a "ver" command'

    # Disconnect from the telnet session
    # Returns None on success; error message on failure.
    def disconnect(self):
        if self.isConnectionOpen:
            self.semaphore.acquire()
            self.sock.close()
            self.semaphore.release()
            self.isConnectionOpen = False
            if self.verboseMode:
                log.warning("Disconnected from " + self.hostname)

    def _sendCommand(self, command, shouldWait=True, doubleTimeout=False):
        # Add a TCP/IP header to the packet. This header is described in the
        # "VR_PMAC_GETRESPONSE" section on page 26
        # of "Accessory 54E Ethernet Protocol User Manual":
        # S:/Technical/Controls/Delta Tau/DLS Motor Controller (Geobrick
        # LV-IMS)/Manuals/acc-54e rev2.pdf
        def getresponseRequest(cmd):
            assert type(cmd) == str
            headerStr = struct.pack("8B", 0x40, 0xBF, 0x0, 0x0, 0x0, 0x0, 0x0, len(cmd))
            wrappedCommand = headerStr + bytes(cmd, "utf-8")
            return wrappedCommand

        def getbufferRequest():
            request = struct.pack(
                "8B", 0xC0, 0xC5, 0x0, 0x0, 0x0, 0x0, 0x08, 0x0
            )  # 0x08,0x0 for a length of 2048; 1400
            # would be 0x05,0x78
            return request

        def receiveReliably(char_num):
            # If socket is interrupted with SIGINT, we need to repeat the
            # receive call.
            # SIGINT has only occured with a Clipper board; the reason for
            # this is unknown.
            while True:
                try:
                    return self.sock.recv(
                        char_num
                    )  # wait for and read the response from PMAC
                    # (will be at most 1400 chars)
                except socket.error as e:
                    if e.errno != errno.EINTR:
                        raise

        try:
            try:
                if shouldWait:
                    self.semaphore.acquire()
                if doubleTimeout:
                    self.sock.settimeout(self.timeout * 2)
                else:
                    self.sock.settimeout(self.timeout)
                # attempt to send the whole packet
                self.sock.sendall(getresponseRequest(command))
                if self.verboseMode:
                    log.error("Sent out: %r" % command)

                # wait for and read the response from PMAC (at most 1400 chars)
                returnStr = receiveReliably(2048).decode()
                if self.verboseMode:
                    log.error("Received: %r" % returnStr)

                short_response = len(returnStr) < 1400
                last_char = returnStr[len(returnStr) - 1]
                response_len = len(returnStr)

                if short_response and (last_char == CHAR_RETURN):
                    # timeout or error allow error responses to pass up
                    pass

                elif short_response and (last_char == CHAR_NULL):
                    # connection lost or PMAC busy
                    raise IOPmacSentNullError(
                        "Did not respond - PMAC busy or connection lost"
                    )

                elif short_response and (last_char != CHAR_ACK) or response_len == 0:
                    raise IOError("PMAC communication error: unexpected terminator")

                elif (
                    short_response
                    and (len(returnStr) > 1)
                    and (returnStr[len(returnStr) - 2] != CHAR_RETURN)
                ):
                    # truncation error in short response
                    raise IOError("Truncated short response")

                # Possible return cases after self.sock.recv(bufsize):
                # 	returnStr[len(returnStr) - 1] == 0x06 (CTRL_F) => DONE.
                # 	returnStr[len(returnStr) - 1] == 0x0D (CTRL_M) =>
                # 	    timeout or error
                # 	neither => continue receiving data
                else:
                    enterLoop = last_char not in VALID_ENDS
                    while enterLoop:
                        self.sock.sendall(getbufferRequest())
                        tmp = self.sock.recv(2048)
                        if len(tmp) < 1400 and tmp[len(tmp) - 1] == 0:
                            raise IOPmacSentNullError("Connection to PMAC lost")
                        returnStr = returnStr + tmp.decode()
                        last_char = returnStr[len(returnStr) - 1]
                        enterLoop = last_char not in VALID_ENDS

                    if last_char == CHAR_RETURN:
                        # stopped looping because of either timeout or error
                        raise IOError("PMAC communication error")

                    if (len(returnStr) > 1) and (
                        returnStr[len(returnStr) - 2] != CHAR_RETURN
                    ):
                        # truncation error in multi-buffer response
                        returnStr = (
                            returnStr[: len(returnStr) - 1]
                            + " WARNING: response truncated."
                            + returnStr[len(returnStr) - 1]
                        )

                return returnStr

            finally:
                if doubleTimeout:
                    self.sock.settimeout(self.timeout)
                if shouldWait:
                    self.semaphore.release()

        except socket.error:
            # Interpret any socket-related error as an I/O error
            raise IOError("Socket communication error")


class PmacTelnetInterface(RemotePmacInterface):
    """Allows connection to a PMAC using a Telnet connection to a terminal
    server session."""

    tn = None

    lstRegExps = [
        # 0: Error message
        re.compile(r"\aERR\d{3}\r".encode("utf8")),
        # 1: One hex number with leading $
        re.compile(r"^\$[A-Z0-9]+\r\x06".encode("utf8")),
        # 2: one decimal number possible sign and possible dot, followed by
        # possible spaces
        re.compile(r"^-?(\d*\.)?\d+\s*\r\x06".encode("utf8")),
        # 3: return value of the status, position, velocity, fol. err command
        # #x?PVF
        re.compile(
            r"^[A-Z0-9]+\r-?(\d*\.)?\d+\r-?(\d*\.)?\d+\r-?(\d*\.)?\d+\r"
            r"\x06".encode("utf8")
        ),
        # 4: everything else... (things not covered above plus commands with
        # no return value)
        re.compile(r"\x06".encode("utf8")),
    ]

    # connect to the telnet session.
    # Returns None if success. Error string if no connection parameters are
    # set or if failure.
    def connect(self, updatesReadyEvent=None):
        self.tn = telnetlib.Telnet()
        if self.hostname:
            try:
                if self.port > 0:
                    self.tn.open(self.hostname, self.port)
                else:
                    self.tn.open(self.hostname)
            except Exception:
                exception_type, _, _ = sys.exc_info()
                if exception_type == socket.gaierror:
                    retStr = (
                        "ERROR: could not open telnet session. Unknown "
                        "host or addressing problem."
                    )
                    log.error(retStr)
                elif exception_type == socket.error:
                    retStr = (
                        "ERROR: could not open telnet session. " "Connection refused."
                    )
                    log.error(retStr)
                else:
                    retStr = "ERROR: Could not open telnet session."
                    log.error(retStr)
                retStr += "\nException thrown: " + str(exception_type)
                self.tn.close()
                return retStr
        else:
            return "ERROR: Could not open telnet session. No hostname set."

        self.isConnectionOpen = True

        # Check flow of serial comm by trying a basic "ver" command (which
        # returns firmware version)
        try:
            self._sendCommand("ver")
        except IOError:
            self.isConnectionOpen = False
            return (
                "Error: did not get expected response from PMAC command "
                '"ver".\n\nMaybe someone is connected to the port '
                "already,\nor you are connecting to a wrong terminal "
                "server port,\nor the port is mis-configured (e.g. wrong "
                "baud rate)."
            )

    # disconnect from the telnet session
    def disconnect(self):
        if self.isConnectionOpen:
            self.isConnectionOpen = False
            self.semaphore.acquire()
            self.tn.close()
            self.semaphore.release()

    # Send a single telnet command to the controller and wait for
    # the expected result returned by the controler.
    def _sendCommand(self, command, shouldWait=True, doubleTimeout=False):
        command = str(command)
        messageTimeout = self.timeout
        if doubleTimeout:
            messageTimeout *= 2

        try:
            try:
                if shouldWait:
                    self.semaphore.acquire()
                    # clear the input queue of orphaned replies to
                    # any previous messages (this can happen if
                    # the previous message timed out before
                    # receiving its reply).
                    if self.tn.sock_avail():
                        orphanedMsg = self.tn.read_very_eager()
                        if self.verboseMode:
                            log.error(
                                "Received unexpected output from PMAC, "
                                "discarding: %r" % orphanedMsg
                            )

                # write the command to PMAC
                self.tn.write((command + "\r\n").encode("utf8"))
                if self.verboseMode:
                    log.error("Sent out: %r" % command)

                # expect a response from the PMAC, satisfying one of the
                # regexes in self.lstRegExps
                (returnMatchNo, returnMatch, returnStr) = self.tn.expect(
                    self.lstRegExps, messageTimeout
                )
                if self.verboseMode:
                    log.error("Received: %r" % returnStr)
                returnStr = returnStr.decode("utf8")
            finally:
                if shouldWait:
                    self.semaphore.release()
        except socket.error as e:
            raise IOError("Communication with PMAC broken: %s" % e)
        except Exception:
            raise IOError("Communication with PMAC broken.")
        if returnMatchNo == -1:
            raise IOError(
                'Timed out waiting for expected response. Got only: "%s"' % returnStr
            )
        else:
            return str(returnStr)


class PmacSerialInterface(RemotePmacInterface):
    """Allows connection to a PMAC via RS232."""

    lstRegExps = [
        # 0: Error message
        re.compile(r"\aERR\d{3}\r"),
        # 1: One hex number with leading $
        re.compile(r"^\$[A-Z0-9]+\r\x06"),
        # 2: one decimal number possible sign and possible dot, followed by
        # possible spaces
        re.compile(r"^-?(\d*\.)?\d+\s*\r\x06"),
        # 3: return value of the status, position, velocity, fol. err command
        # #x?PVF
        re.compile(r"^[A-Z0-9]+\r-?(\d*\.)?\d+\r-?(\d*\.)?\d+\r-?(\d*\.)?\d+\r\x06"),
        # 4: everything else... (things not covered above plus commands with
        # no return value)
        re.compile(r"\x06"),
    ]

    # connect to the telnet session.
    # Returns None if success. Error string if no connection parameters are
    # set or if failure.
    def connect(self, updatesReadyEvent=None):
        """Connect here"""
        # used same class attributes as other PMAC classes for getting data
        # from GUI...lazy and confusing here!
        self.baud_rate = self.port
        self.comm_port = self.hostname

        self.last_received_packet = ""
        self.last_comm_time = 0.0
        self.n_timeouts = 0
        # self.transmission_delay = 0.0001 #1.2*9.0/float(self.baud_rate)
        try:
            self.serial = serial.Serial(
                self.comm_port,
                self.baud_rate,
                timeout=self.timeout,
                rtscts=True,
                dsrdtr=True,
            )
        except serial.serialutil.SerialException:
            return "Port already in use!"

        if self.isConnectionOpen:
            return "Socket is already open"

        self.isConnectionOpen = True

        # Check flow of serial comm by trying a basic "ver" command (which
        # returns firmware version)
        try:
            self._sendCommand("ver")
        except IOError as e:
            self.isConnectionOpen = False
            msg = "send failed"
            log.debug(msg, exc_info=True)
            # log.error(msg)
            raise e
            # return "Error: did not get expected response from PMAC command
            # \"ver\".\n\nMaybe someone is connected to the port already,
            # \nor you are connecting to a wrong serial port,\nor the port is
            # misconfigured (e.g. wrong baud rate)."

    # disconnect from the telnet session
    def disconnect(self):
        if self.isConnectionOpen:
            self.isConnectionOpen = False
            self.semaphore.acquire()
            self.serial.close()
            self.semaphore.release()

    # Send a single telnet command to the controller and wait for
    # the expected result returned by the controler.
    def _sendCommand(self, command, shouldWait=True, doubleTimeout=False):
        command = str(command)
        messageTimeout = self.timeout
        if doubleTimeout:
            messageTimeout *= 2

        try:
            try:
                if shouldWait:
                    self.semaphore.acquire()
                comms_start = time.time()
                # clear the input queue of orphaned replies to
                # any previous messages (this can happen if
                # the previous message timed out before
                # receiving its reply).
                if self.serial.inWaiting():
                    orphanedMsg = self.serial.readline()
                    if self.verboseMode:
                        log.error(
                            "Received unexpected output from PMAC, "
                            "discarding: %r" % orphanedMsg
                        )

                # write the command to PMAC
                command = command + "\r"
                for letter in command:
                    self.serial.write(letter)
                    # need to enforce pause to allow for transmission time of
                    # characters (for Clipper at least)
                    # time.sleep(self.transmission_delay)
                if self.verboseMode:
                    log.error("Sent out: %r" % command)

                # read reply one character at a time, stopping at terminate
                # char '\x06' or if timeout is exceeded
                # N.B. probably could do this more robustly/quickly with file
                # i/o or built-ins
                returnStr = ""
                char = ""
                read_start = time.time()
                while char != "\x06" and time.time() - read_start < messageTimeout:
                    char = self.serial.read()
                    returnStr = returnStr + char.decode()
                # print(returnStr)
                returnMatchNo = [
                    x for x in range(0, 5) if self.lstRegExps[x].search(returnStr)
                ]

                if time.time() - read_start > messageTimeout:
                    self.n_timeouts = self.n_timeouts + 1
                    log.error("Warning: Communication Timeout! (#%s)" % self.n_timeouts)

                if returnMatchNo == [0]:
                    log.error(
                        "PMAC returned error: %s (%s)"
                        % (returnStr[1:-1], self.PMAC_errors[returnStr[1:-1]])
                    )
                elif self.verboseMode:
                    if not returnMatchNo:
                        log.error('Bad or no response from PMAC: "%s"', returnStr)
                    else:
                        log.error(
                            "Received: %r (total duration %s seconds, %s)"
                            % (returnStr, str(time.time() - comms_start), returnMatchNo)
                        )
                self.last_comm_time = time.time()
            finally:
                if shouldWait:
                    self.semaphore.release()
        except serial.SerialException as e:
            errorMsg = e
            raise IOError("Communication with PMAC broken: %s" % errorMsg)

        return str(returnStr)


# \file
# \section License
# Author: Diamond Light Source, Copyright 2011
#
# 'dls_pmaclib' is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'dls_pmaclib' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with 'dls_pmaclib'.  If not, see http://www.gnu.org/licenses/.
