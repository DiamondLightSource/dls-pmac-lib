#!/bin/env dls-python2.6

import sys, re, socket, select, random, struct
import threading, time
import telnetlib

class RemotePmacInterface:
	'''This class provides a common interface to a remote PMAC. It provides methods
           to connect to the PMAC (e.g. via a Telnet terminal server
	   session or Ethernet), to disconnect, and to issue commands. It provides
           methods for some basic axis commands (e.g. move/jog axis etc.).  It is
           a base class that should not be instantiated directly.'''
	def __init__(self, parent = None, verbose = False, numAxes = None, timeout = 3.0):
		# Basic connection settings
		self.verboseMode = verbose
		self.hostname = ""
		self.port = None
		self.parent = parent

		# Access-to-the-connection semaphore. Use this to lock/unlock I/O access to the connection (whatever type it is) in child classes.
		self.semaphore = threading.Semaphore()

		self.isConnectionOpen = False
                self.timeout = timeout

		# Use the getter self.isModelGeobrick() to access this. The value is None if uninitialised.
		self._isModelGeobrick = None

		# Use the getter self.getNumberOfAxes() to access this. The value is None if uninitialised.
		if numAxes is not None:
			self._numAxes = int(numAxes)
		else:
			self._numAxes = None

		self.MACRO_STATION_LOOKUP_TABLE = [0,1,4,5,8,9,12,13,16,17,20,21,24,25,28,29,32,33,36,37,40,41,44,45,48,49,52,53,56,57,60,61,64,65]

	def setConnectionParams(self, host = "localhost", port = None):
		self.hostname = str(host)
		if port:
			self.port = int(str(port))
		else:
			self.port = None

	# Connect to the host
	# Returns None if success. Error string if no connection parameters are set or if failure.
	def connect( self, updatesReadyEvent=None ):
		raise NotImplementedError('This method must be implemented in child classes')

	# disconnect from the host
	def disconnect(self):
		raise NotImplementedError('This method must be implemented in child classes')

	# Send a single command to the controller and block until a response from the controller.
	# This is a return-format wrapper for the _sendCommand() method, written as the existing code uses this
	# form of sendCommand() a lot.
	# Arguments: * command (str): is the command to be sent
	#			* shouldWait (bool, optional, default True): whether to wait on the semaphore.
	#			  This should normally be left default. If we have acquired the semaphore manually,
	#			  then specify shouldWait = False (and don't forget to release the semaphore eventually).
	# Returns: A tuple (response, wasSuccessful), where:
	#		  * wasSuccessful (bool): is True unless there was an I/O problem during comm with the PMAC
	#								  or the response does not have recognised terminators.
	#								  Note that PMAC may still return an "ERRxxx" code; this function will still
	#								  consider that a successful transmission.
	#		  * response (str): is either a string returned by the PMAC (on success), or an error message (on failure)
	def sendCommand(self, command, shouldWait = True):
		# Submit the command to the low level function _sendCommand().
		# If I/O with the PMAC fails, return as a failure case.
		command = str(command)
                doubleTimeout = self.commandNeedsDoubleTimeout(command)
		(success, failure) = (True, False)
		try:
			response = self._sendCommand(command, shouldWait = shouldWait, doubleTimeout = doubleTimeout)
		except IOError, e:
			return ('I/O error during comm with PMAC: %s' % str(e), failure)
		return (response, success)

	# Send a single command to the controller and block until a response from the controller.
	# This is the actual method that does the I/O with the remote PMAC, and needs to be overriden in a child class;
	# each read/write cycle should be implemented to block.
	# Returns: a string with PMAC's response to the command.
	# Throws: an IOError if any I/O-related error occured.
	def _sendCommand(self, command, shouldWait = True, doubleTimeout = False):
		raise NotImplementedError('This method must be implemented by one of the child classes')

	# Turn on the modbus on the PMAC to allow spinlocks on the device
	def enablePmacLocking(self):
		raise NotImplementedError('This method must be implemented by one of the child classes')

	# Turn off the modbus on the PMAC to disable spinlocks on the device
	def disablePmacLocking(self):
		raise NotImplementedError('This method must be implemented by one of the child classes')

	# Check if the modbus on the PMAC is enabled, i.e. if spinlocks are possible
	def pmacLockingEnabled(self):
		raise NotImplementedError('This method must be implemented by one of the child classes')

	# Return a string designating which PMAC model this is, or None on error
	def getPmacModel(self):
		# Ask for pmac model, returns an integer
		(retStr, wasSuccessful) = self.sendCommand('cid')
		if not wasSuccessful:
			raise IOError('Error talking to PMAC')
		mo = re.compile('^(\d+)\r\x06$').match(retStr)
		if mo:
			modelCode = int(mo.group(1))
		else:
			raise ValueError('Received malformed input from PMAC (%r)' % retStr)

		# Return a model designation based on model code
		modelNamesByCode = {
			602413: 'Turbo PMAC2-VME',
			603382: 'Geo Brick (3U Turbo PMAC2)'
			}
		try:
			modelName = modelNamesByCode[modelCode]
		except KeyError:
			raise ValueError('Unsupported PMAC model')

		return modelName

	def isModelGeobrick(self):
		if self._isModelGeobrick == None:
			# If self._isModelGeobrick is not initialised, do so now
			self._isModelGeobrick = self.getPmacModel() == 'Geo Brick (3U Turbo PMAC2)'
		return self._isModelGeobrick

	# Get the number of macro stations available. This is given by number of Macro ICs available. One MACRO IC can control up to 8 axes,
	# so the number returned is a multiple of 8. The availability of MACRO ICs is determined by querying I20..23 (read-only variables).
	# The first MACRO IC is available if I20 (MACRO IC base address) is non-zero.
	# The second, third, and fourth MACRO IC are similarly addressed by I21, I22, I23.
	def _getNumberOfMacroStationAxes(self):
		macroIcAddresses = self.getIVars(0, [20,21,22,23])  # access I20..23
		if self.verboseMode:
			print 'Got MACRO IC station base addresses: %s ($0 means not present)' % str(macroIcAddresses)
		controllableAxesCount = 0
		for i in range(4):
			if macroIcAddresses[i] != '$0':
				controllableAxesCount += 8
		return controllableAxesCount

	# Get the total number of axes available
	def getNumberOfAxes(self):
		if self._numAxes == None:
			if self.isModelGeobrick():
				self._numAxes = 8 + self._getNumberOfMacroStationAxes()
			else:
				self._numAxes = self._getNumberOfMacroStationAxes()
		if self.verboseMode:
			print 'Total number of axes is %d.' % self._numAxes
		return self._numAxes

	def checkAxisIsInRange(self, axis):
		if axis < 0:
			raise ValueError('Asking for a negative axis')
		if axis > self.getNumberOfAxes():
			raise ValueError('Requested axis %d but PMAC has only %d axes' % (axis, self.getNumberOfAxes()))

	# Returns: Macro station number
	# Raises: ValueError if asking for non-existent axis, or not a MACRO ring axis
	def getAxisMacroStationNumber(self, axis):
		self.checkAxisIsInRange(axis)
		if not self.isModelGeobrick():
			return self.MACRO_STATION_LOOKUP_TABLE[axis - 1]
		else:
			if axis <= 8:
				raise ValueError('Axis %d is not on the MACRO ring' % axis)
			else:
				return self.MACRO_STATION_LOOKUP_TABLE[(axis - 8) - 1]

	# Return True if this is a macro station axis, False if it is an on-board-PMAC axis
	def isMacroStationAxis(self, axis):
		self.checkAxisIsInRange(axis)
		if not self.isModelGeobrick():
			return True
		else:
			return axis > 8

	# Get a list of values of Ixxxx variables, where xxxx = base + offset (for each offset).
	def getIVars(self, base, offsets):
		iVars = map(lambda x: base + x, offsets)
		cmd = ""
		for iVar in iVars:
			cmd += "i%d " % iVar
		(retStr, status) = self.sendCommand(cmd)
		if status:
			return retStr.split('\r')[:-1]
		else:
			raise IOError('Cannot retrieve variable: error communicating with PMAC')

	def setVar(self, varName, value):
		(returnStr, wasSuccessful) = self.sendCommand('%s=%s' % (varName, str(value)))
		if not wasSuccessful:
			raise IOError('Cannot set variable: error communicating with PMAC')

	# Get a list of values of the "Setup I-variables" for a particular axis.
	# The "Setup I-variables" (thus named in the PMAC Software Reference Manual) are the ones in the Ixxyy range, where xx = axis number, yy = offset.
	# E.g. I one wants variables Ixx30, Ixx31 and Ixx32 for axis 14, the should call self.getAxisISetupVars(14, [30,31,32]).
	def getAxisSetupIVars(self, axis, offsets):
		self.checkAxisIsInRange(axis)
		base = 100 * axis
		return self.getIVars(100 * axis, offsets)

	def setAxisSetupIVar(self, axis, offset, value):
		self.checkAxisIsInRange(axis)
		iVar = 100 * axis + offset
		self.setVar('i%d' % iVar, value)

	# Get macro station I-variables for a particular axis (or None on failure)
	def getAxisMsIVars(self, axis, msIVars):
		self.checkAxisIsInRange(axis)
		macroStationNo = self.getAxisMacroStationNumber(axis)
		cmd = ""
		for msIVar in msIVars:
			cmd += "ms%d,i%d " % (macroStationNo, msIVar)
		(retStr, status) = self.sendCommand(cmd)
		if status:
			return retStr.split('\r')[:-1]
		else:
			raise IOError('Cannot retrieve variable: error communicating with PMAC')

	def setAxisMsIVar(self, axis, iVar, value):
		self.checkAxisIsInRange(axis)
		macroStationNo = self.getAxisMacroStationNumber(axis)
		self.setVar('ms%d,i%d' % (macroStationNo, iVar), value)

	# Calculate the base I-variable number in the I70mn (say, "I7000+") range for an onboard Geobrick axis.
	# For axes 1, 2, ... the bases are 7000, 7010, 7020, 7030, 7100, 7110, 7120, 7130.
	def getOnboardAxisI7000PlusVarsBase(self, axis):
		# If not a Geobrick axis, raise an exception
		self.checkAxisIsInRange(axis)
		if self.isMacroStationAxis(axis):
			raise ValueError('Axis %d is not an onboard axis' % axis)

		# Calculate the base
		m = (axis-1) / 4		# m in 0..9
		n = (axis-1) % 4 + 1	# n in 1..4
		base = 7000 + m * 100 + n * 10
		return base

	def getOnboardAxisI7000PlusVars(self, axis, offsets):
		iVarsBase = self.getOnboardAxisI7000PlusVarsBase(axis)
		return self.getIVars(iVarsBase, offsets)

	def setOnboardAxisI7000PlusIVar(self, axis, offset, value):
		base = self.getOnboardAxisI7000PlusVarsBase(axis)
		iVar = base + offset
		self.setVar('i%d' % iVar, value)

 	# function that sends out a whole list of commands to the pmac
	# (like from a file...). The function waits for a response from each command
	# and register any errors returned.
	# After a command has been sent and a response received, the function will post an event
	# to update the progress dialog in the main (GUI) thread.
	# cmdLst is a list of tuples: (lineNumber, command)
	# where command is the command from the file and lineNumber
	# is the line number from the original file.
	def sendSeries(self, cmdLst):
		errRegExp = re.compile(r'ERR\d{3}')

		# Acquire the semaphore controlling access to the connection
		self.semaphore.acquire()
		if self.verboseMode:
			print '\n\n\n\nGot the semaphore!\n\n\n\n'

		for i, cmd in enumerate(cmdLst):
			# Send one line from to the controller.
			# Because we have acquired the semaphore already, we do not wait for it again.
			(lineNumber, command) = cmd
			(pmacResponseStr, wasSuccessful) = self.sendCommand(command, shouldWait = False)
			# Check if PMAC returns an error as a response; if so, append the error message to the error list
			if not wasSuccessful or errRegExp.findall(pmacResponseStr):
				wasSuccessful = False

			# yield control back
			try:
				yield (wasSuccessful, lineNumber, command, pmacResponseStr)
			except GeneratorExit:
				# user cancelled operation
				self.semaphore.release()
				if self.verboseMode:
					print '\n\n\n\nReleased the semaphore because of cancellation!\n\n\n\n'
				return

		# Release the semaphore controlling access to the connection
		self.semaphore.release()
		if self.verboseMode:
			print '\n\n\n\nReleased the semaphore!\n\n\n\n'

        # Controls whether to wait for double the normal timeout for this 
        # message. Currently only used for the SAVE command.
        def commandNeedsDoubleTimeout(self, command):
                return 'SAVE' in command.upper()

	# Jog incrementally
	# \motor the motor number to jog.
	# \direction string either "pos" or "neg"
	# \distance in counts
	def jogInc(self, motor, direction, distance):
		if direction == "neg":
			cmd = "#" + str(motor) + "J^-" + str(distance)
		elif direction == "pos":
			cmd = "#" + str(motor) + "J^" + str(distance)
		else: return (cmd, "Error, could not recognise direction: " + str(direction), False)

		(retStr, retStatus) = self.sendCommand( cmd )
		return (cmd, retStr, retStatus)

	def jogStop(self, motor):
		cmd = "#" + str(motor) + "J/"
		(retStr, retStatus) = self.sendCommand( cmd )
		return (cmd, retStr, retStatus)

	def jogTo(self, motor, newposition):
		cmd = "#" + str(motor) + "J=" + str(newposition)
		(retStr, retStatus) = self.sendCommand( cmd )
		return (cmd, retStr, retStatus)

	def jogContinous(self, motor, direction):
		if direction == "neg":
			cmd = "#" + str(motor) + "J-"
		elif direction == "pos":
			cmd = "#" + str(motor) + "J+"
		else: return (cmd, "Error, could not recognise direction: " + str(direction), False)

		(retStr, retStatus) = self.sendCommand( cmd )
		return (cmd, retStr, retStatus)

	def homeCommand(self, motor):
		cmd = "#"+str(motor)+"HM"
		(retStr, retStatus) = self.sendCommand( cmd )
		return (cmd, retStr, retStatus)

	def disableLimits(self, motor, disable):
		motor = str(motor)
		(retStr, status) = self.sendCommand( "i"+motor+"24")
		if not status:
			return 1

		#print (retStr, status)
		initialLimits = int( retStr.strip('$\r\x06'), 16)
		currentlyEnabled = bool( not (initialLimits & 0x20000) )

		if currentlyEnabled and disable:
			# Disable limits
			limitSetting = initialLimits | 0x20000
		elif (not currentlyEnabled) and (not disable):
			# enable limits
			limitSetting = initialLimits ^ 0x20000
		else: return ('','',False)
		cmd = "i"+motor+"24="+hex(limitSetting).replace('0x', '$')
		(retStr, status) = self.sendCommand( cmd )
		return (cmd, retStr, status)

	def testSendCommand(self):
		(str, code) = self.sendCommand('i20')
		print 'i20: %r' % str
		(str, code) = self.sendCommand('nonsense')
		print 'nonsense: %r' % str
		(str, code) = self.sendCommand('i20..23')
		print 'i20..23: %r' % str

	# ---------------------------------------------------------- Tests ----------------------------------------------------------
	# A very basic test framework. Prints out test results onto standard output.
	# Run pmac.runTests() on a newly created pmac = PmacRemoteInterface(...) object, which is already successfully connect()-ed.

	def testGetAxisMacroStationNumber(self):
		for i in range(1,33):
			try:
				print 'pmac.getAxisMacroStationNumber(%d) returns %s.' % (i, repr(self.getAxisMacroStationNumber(i)))
			except Exception, e:
				print 'pmac.getAxisMacroStationNumber(%d) raised %s' % (i, str(e))

	def testIsMacroStationAxis(self):
		for i in range(1,33):
			try:
				print 'pmac.isMacroStationAxis(%d) returns %s.' % (i, repr(self.isMacroStationAxis(i)))
			except Exception, e:
				print 'pmac.isMacroStationAxis(%d) raised %s' % (i, str(e))

	def runTests(self):
		print '______________________________________'
		self.testSendCommand()
		print 'pmac.isModelGeobrick() returns %s' % str(self.isModelGeobrick())
		self.getNumberOfAxes()
		self.testIsMacroStationAxis()
		self.testGetAxisMacroStationNumber()

class PmacEthernetInterface(RemotePmacInterface):
	'''Allows connection to a PMAC over an Ethernet interface.'''

	# Attempts to open a connection to a remote PMAC.
	# Returns None on success, or an error message string on failure.
	def connect(self):

		# Sanity checks
		if self.isConnectionOpen:
			return 'Socket is already open'
		if self.hostname in (None, '') or self.port in (None, 0):
			return 'ERROR: hostname or port number not set'

		# Create a new socket instance
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		#self.sock.setblocking(1) # N.B.: line is pointless because the next one overrides it
		self.sock.settimeout(self.timeout)

		# Attempt to establish a connection to the remote host
		try:
			if self.verboseMode:
				print 'Connecting a socket to host "%s" using port %d' % (self.hostname, self.port)
			self.sock.connect( (self.hostname, self.port) )
			if self.verboseMode:
				print 'Connected to host "%s" on port %d' % (self.hostname, self.port)
		except socket.gaierror:
			return 'ERROR: unknown host'
		except:
			return 'ERROR: connection refused by host'

		self.isConnectionOpen = True

		# Check that the we are connected to a pmac by issuing the "ver" command -- expecting the 1.922 in return.
		#If we don't get the right response, then disconnect automatically
		try:
			if self.verboseMode:
				print 'Testing connection...'
			response = self._sendCommand('ver')
			if self.verboseMode:
				print '\tDevice responding.' + response
		except IOError:
			self.disconnect()
			return 'Device failed to respond to a "ver" command'
		if not re.match('^\d+\.\d+\s*\r\x06$',response):
			# if the response is not of the form "1.945  \r\x06" then we're not talking to a PMAC!
			self.disconnect()
			return 'Device did not respond correctly to a "ver" command'

	# Disconnect from the telnet session
	# Returns None on success; error message on failure.
	def disconnect(self):
		if self.isConnectionOpen:
                        self.releasePmacSpinlock()
			self.semaphore.acquire()
			self.sock.close()
			self.semaphore.release()
			self.isConnectionOpen = False
			if self.verboseMode:
				print 'Disconnected from ' + self.hostname

	def _sendCommand(self, command, shouldWait = True, doubleTimeout = False):
		# Add a TCP/IP header to the packet. This header is described in the "VR_PMAC_GETRESPONSE" section on page 26
		# of "Accessory 54E Ethernet Protocol User Manual":
		# S:/Technical/Controls/Delta Tau/DLS Motor Controller (Geobrick LV-IMS)/Manuals/acc-54e rev2.pdf
		def getresponseRequest(command):
			assert type(command) == str
			headerStr = struct.pack('8B',0x40,0xBF,0x0,0x0,0x0,0x0,0x0,len(command))
			wrappedCommand = headerStr + command
			return wrappedCommand

		def getbufferRequest():
			request = struct.pack('8B',0xC0,0xC5,0x0,0x0,0x0,0x0,0x08,0x0) # 0x08,0x0 for a length of 2048; 1400 would be 0x05,0x78
			return request

		try:
			try:
				self.acquirePmacSpinlock(shouldWait)
                                if shouldWait:
					self.semaphore.acquire()
                                if doubleTimeout:
                                        self.sock.settimeout(self.timeout*2)
                                else:
                                        self.sock.settimeout(self.timeout)

				self.sock.sendall(getresponseRequest(command)) # attept to send the whole packet
				if self.verboseMode:
					print 'Sent out: %r' % command

				returnStr = self.sock.recv(2048) # wait for and read the response from PMAC (will be at most 1400 chars)

				short_response = len(returnStr) < 1400

				if short_response and (returnStr[len(returnStr) - 1] == '\x0D'):
					raise IOError('PMAC communication error') # timeout or error

				if short_response and (returnStr[len(returnStr) - 1] == '\x00'):
					raise IOError('Connection to PMAC lost') # connection lost

				if short_response and (returnStr[len(returnStr) - 1] != '\x06'):
					raise IOError('Malformed response') # weird error

				short_response = short_response and (len(returnStr) > 1)
				if short_response and (returnStr[len(returnStr) - 2] != '\r'):
					raise IOError('Truncated short response') # truncation error in short response

				# Possible return cases after self.sock.recv(bufsize):
				# 	returnStr[len(returnStr) - 1] == 0x06 (CTRL_F) => DONE.
				# 	returnStr[len(returnStr) - 1] == 0x0D (CTRL_M, '\r') => timeout or error
				# 	neither => continue receiving data
				enterLoop = (returnStr[len(returnStr) - 1] != '\x06')
                                enterLoop = enterLoop and (returnStr[len(returnStr) - 1] != '\x0D')
				while enterLoop:
					self.sock.sendall(getbufferRequest())
                                        tmp = self.sock.recv(2048)
                                        if len(tmp) < 1400 and tmp[len(tmp) - 1] == '\x00':
						raise IOError('Connection to PMAC lost')
					returnStr = returnStr + tmp
					enterLoop = (returnStr[len(returnStr) - 1] != '\x06')
                                        enterLoop = enterLoop and (returnStr[len(returnStr) - 1] != '\x0D')

				if returnStr[len(returnStr) - 1] == '\x0D': # stopped looping because of either timeout or error
					raise IOError('PMAC communication error')

				if (len(returnStr) > 1) and (returnStr[len(returnStr) - 2] != '\r'): # truncation error in multi-buffer response
					returnStr = returnStr[:len(returnStr) - 1] + ' WARNING: response truncated.' + returnStr[len(returnStr) - 1]

				return returnStr
			finally:
                                if doubleTimeout:
                                        self.sock.settimeout(self.timeout)
				if shouldWait:
					self.semaphore.release()
                                self.releasePmacSpinlock(shouldWait)
		except socket.error:
			# Interpret any socket-related error as an I/O error
			raise IOError('Socket communication error')

	# acquire a spinlock for the PMAC itself
	def acquirePmacSpinlock(self, shouldWait = True):
		try:
			lockCommand = struct.pack('8B',0x40,0xD7,0x0,0x01,0x0,0x0,0x0,0x0)
			if shouldWait:
				self.semaphore.acquire()
			self.sock.sendall(lockCommand)
			#if self.verboseMode:
				#print 'Lock command sent.'
			read_ready,_,_ = select.select([self.sock], [], [], 2.0)
			while not read_ready:
				self.sock.sendall(lockCommand)
				#if self.verboseMode:
					#print 'Re-sent lock command.'
				read_ready,_,_ = select.select([self.sock], [], [], 2.0)
			response = self.sock.recv(2048)
			#if self.verboseMode:
				#print 'Recieved response.'
			if shouldWait:
				self.semaphore.release()
		except socket.error:
			# Interpret any socket-related error as an I/O error
			raise IOError('Socket communication error trying to acquire spinlock')

	# release a previously acquired spinlock for the PMAC itself
	def releasePmacSpinlock(self, shouldWait = True):
		try:
			unlockCommand = struct.pack('8B',0x40,0xD7,0x0,0x0,0x0,0x0,0x0,0x0)
			if shouldWait:
				self.semaphore.acquire()
			self.sock.sendall(unlockCommand)
			response = self.sock.recv(2048)
			if shouldWait:
				self.semaphore.release()
		except socket.error:
			# Interpret any socket-related error as an I/O error
			raise IOError('Socket communication error trying to release spinlock')

	# Turn on the modbus on the PMAC to allow spinlocks on the device
	def enablePmacLocking(self):
		try:
			self.sendCommand('def ubuf 256')
			self.sendCommand('i67=i4908')
			(s,_) = self.sendCommand('i67')
			i67 = int(s.rstrip('\x06').rstrip('\r').lstrip('$'))
			self.sendCommand('wl:$%r,$100000000000' % i67)
			i67 = i67 + 3
			self.sendCommand('wl:$%r,$100000000000' % i67)
			i67 = i67 + 3
			self.sendCommand('wl:$%r,$100000000000' % i67)
			i67 = i67 + 3
			self.sendCommand('wl:$%r,$100000000000' % i67)
			self.sendCommand('i69=i67+$70')
			self.sendCommand('save')
		except socket.error:
			# Interpret any socket-related error as an I/O error
			raise IOError('Socket communication error')

	# Turn off the modbus on the PMAC to disable spinlocks on the device
	def disablePmacLocking(self, shouldWait = True):
		try:
                        self.acquirePmacSpinlock()

			# Lock-free equivalent of (s, code) = self.sendCommand('i69=0')
                        request = struct.pack('8B',0x40,0xBF,0x0,0x0,0x0,0x0,0x0,len('i69=0'))
                        request = request + 'i69=0'
                        if shouldWait:
				self.semaphore.acquire()
			self.sock.sendall(request)
			response = self.sock.recv(2048)
			if shouldWait:
				self.semaphore.release()

			# Lock-free equivalent of (s, code) = self.sendCommand('def ubuf 0')
                        request = struct.pack('8B',0x40,0xBF,0x0,0x0,0x0,0x0,0x0,len('def ubuf 0'))
                        request = request + 'def ubuf 0'
                        if shouldWait:
				self.semaphore.acquire()
			self.sock.sendall(request)
			response = self.sock.recv(2048)
			if shouldWait:
				self.semaphore.release()

			# Lock-free equivalent of (s, code) = self.sendCommand('i67=0')
                        request = struct.pack('8B',0x40,0xBF,0x0,0x0,0x0,0x0,0x0,len('i67=0'))
                        request = request + 'i67=0'
                        if shouldWait:
				self.semaphore.acquire()
			self.sock.sendall(request)
			response = self.sock.recv(2048)
			if shouldWait:
				self.semaphore.release()

			# Lock-free equivalent of (s, code) = self.sendCommand('save')
                        request = struct.pack('8B',0x40,0xBF,0x0,0x0,0x0,0x0,0x0,len('save'))
                        request = request + 'save'
                        if shouldWait:
				self.semaphore.acquire()
			self.sock.sendall(request)
			response = self.sock.recv(2048)
			if shouldWait:
				self.semaphore.release()

                        self.releasePmacSpinlock()
		except socket.error:
			# Interpret any socket-related error as an I/O error
			raise IOError('Socket communication error')

	# Check if the modbus on the PMAC is enabled, i.e. if spinlocks are possible
	def pmacLockingEnabled(self):
		(i67, success) = self.sendCommand('i67')
		if success:
			i67 = int(i67.rstrip('\x06').rstrip('\r').lstrip('$'))
			if i67 == 0:
				return False
			else:
				return True
		else:
			raise IOError('Communication error')


class PmacTelnetInterface(RemotePmacInterface):
	'''Allows connection to a PMAC using a Telnet connection to a terminal server session.'''

	lstRegExps = [
		# 0: Error message
		re.compile( r'\aERR\d{3}\r' ),
		# 1: One hex number with leading $
		re.compile( r'^\$[A-Z0-9]+\r\x06' ),
		# 2: one decimal number possible sign and possible dot, followed by possible spaces
		re.compile( r'^-?(\d*\.)?\d+\s*\r\x06' ),
		# 3: return value of the status, position, velocity, fol. err command #x?PVF
		re.compile( r'^[A-Z0-9]+\r-?(\d*\.)?\d+\r-?(\d*\.)?\d+\r-?(\d*\.)?\d+\r\x06' ),
		# 4: everything else... (things not covered above plus commands with no return value)
		re.compile( r'\x06' )
	]

	# connect to the telnet session.
	# Returns None if success. Error string if no connection parameters are set or if failure.
	def connect( self):
		self.tn = telnetlib.Telnet()
		if self.hostname:
			try:
				if self.port > 0:
					self.tn.open( self.hostname, self.port )
				else:
					self.tn.open( self.hostname )
			except:
				if sys.exc_type == socket.gaierror:
					retStr = "ERROR: could not open telnet session. Unknown host or addressing problem."
					print retStr
				elif sys.exc_type == socket.error:
					retStr = "ERROR: could not open telnet session. Connection refused."
					print retStr
				else:
					retStr = "ERROR: Could not open telnet session."
					print retStr
				retStr += "\nException thrown: "+str(sys.exc_type)
				self.tn.close()
				return retStr
		else:
			return "ERROR: Could not open telnet session. No hostname set."

		self.isConnectionOpen = True

		# Check flow of serial comm by trying a basic "ver" command (which returns firmware version)
		try:
			response = self._sendCommand("ver")
		except IOError:
			self.isConnectionOpen = False
			return "Error: did not get expected response from PMAC command \"ver\".\n\nMaybe someone is connected to the port already,\nor you are connecting to a wrong terminal server port,\nor the port is misconfigured (e.g. wrong baud rate)."

	# disconnect from the telnet session
	def disconnect(self):
		if self.isConnectionOpen:
			self.isConnectionOpen = False
			self.semaphore.acquire()
			self.tn.close()
			self.semaphore.release()

	# Send a single telnet command to the controller and wait for
	# the expected result returned by the controler.
	def _sendCommand( self, command, shouldWait = True, doubleTimeout = False):
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
                                                print "Received unexpected output from PMAC, discarding: %r" % orphanedMsg

				# write the command to PMAC
				self.tn.write( command  + '\r\n')
				if self.verboseMode:
					print 'Sent out: %r' % command

				# expect a response from the PMAC, satisfying one of the regexes in self.lstRegExps
				(returnMatchNo, returnMatch, returnStr) = self.tn.expect( self.lstRegExps, messageTimeout)
				if self.verboseMode:
                                        print 'Received: %r' % returnStr

                        finally:
                                if shouldWait:
                                        self.semaphore.release()
		except socket.error, e:
			errorMsg = e[1]
			raise IOError('Communication with PMAC broken: %s' % errorMsg)
		except:
			raise IOError('Communication with PMAC broken.')
		if returnMatchNo == -1:
			raise IOError('Timed out waiting for expected response. Got only: ' + str(returnStr))
		else:
			return str(returnStr)

	# Turn on the modbus on the PMAC to allow spinlocks on the device
	def turnPmacLockingOn(self):
		#This feature only makes sense for Ethernet interfaces
		raise NotImplementdError('This feature is only available to sister class PmacEthernetInterface.')

	# Turn off the modbus on the PMAC to disable spinlocks on the device
	def turnPmacLockingOff(self):
		#This feature only makes sense for Ethernet interfaces
		raise NotImplementdError('This feature is only available to sister class PmacEthernetInterface.')

	# Check if the modbus on the PMAC is enabled, i.e. if spinlocks are possible
	def pmacLockingEnabled(self):
		return False

## \file
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
