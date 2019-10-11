from logging import getLogger

log = getLogger("dls_pmaclib")

WORD = 24
LONGWORD = 48
# initialise the data addresses that the PMAC can gather from
motorBaseAddrs = [0x080, 0x100, 0x180, 0x200, 0x280, 0x300, 0x380, 0x400,
                  0x480, 0x500, 0x580, 0x600, 0x680, 0x700, 0x780, 0x800,
                  0x880, 0x900, 0x980, 0xA00, 0xA80, 0xB00, 0xB80, 0xC00,
                  0xC80, 0xD00, 0xD80, 0xE00, 0xE80, 0xF00, 0xF80, 0x1000]

dataSources = [
    {"reg": 0x08,
     "desc": "Motor present desired position",
     "unit": "cts]",
     "size": 0x8,
     "scalingCalc": "1.0/(%d*32.0)",
     "scalingIvars": ("i%d08",)},

    {"reg": 0x0B,
     "desc": "Motor present actual position",
     "unit": "[cts]",
     "size": 0x8,
     "scalingCalc": "1.0/(%d*32.0)",
     "scalingIvars": ("i%d08",)},

    {"reg": 0x11,
     "desc": "Motor following error",
     "unit": "[cts]",
     "size": 0x8,
     "scalingCalc": "1.0/(%d*32.0)",
     "scalingIvars": ("i%d08",)},

    {"reg": 0x1D,
     "desc": "Motor present actual velocity (unfiltered)",
     "unit": "[cts/servo cycle]",
     "size": 0x4,
     "scalingCalc": "1.0/(%d*32.0)/(%d+1)",
     "scalingIvars": ("i%d09", "i%d60")}
]


class GatherChannel:
    def __init__(self, pmac):
        self.axisNo = None
        self.pmac = pmac

        # Define the data arrays that each channel will maintain
        self.strData = []
        self.rawData = []
        self.scaledData = []

        # Data source I variable (5001-5048)
        # and data source address
        self.pSrcIvar = None
        self.srcDataAddr = ""

        # Information about the data
        self.dataWidth = 0  # How many bits wide
        self.dataType = None  # float or int
        self.regOffset = None  # The data offset from the motor base address
        # (i.e. what the data represents physically: pos, velo, foll. osv osv)
        self.dataSourceInfo = None  # data source dict (from global dataSources)

        self.scalingFactor = None

    def setDataGatherPointer(self, ivar):
        self.pSrcIvar = ivar
        return

    # Read the address of a gather I variable and interpret the
    # address to determine: datawidth, datatype, unit and scaling factor
    # result is returned in a dictionary
    def getDataInfo(self, address=None):

        if address:
            addr = address
        else:
            # read the gather I variable from the pmac
            (ret_word, status) = self.pmac.sendCommand(self.pSrcIvar)
            if not status:
                return
            # remove newline
            addr = ret_word[0:-1]

        # Get the data width and type from the first digit in the hex-value
        lenWord = addr.strip('$')[0]
        if lenWord == '0' or lenWord == '4':
            self.dataWidth = WORD
            self.dataType = int
        elif lenWord == '8':
            self.dataWidth = LONGWORD
            self.dataType = int
        elif lenWord == 'C':
            self.dataWidth = LONGWORD
            self.dataType = float
        else:
            log.error("### Error: Could not get data width and type from: %s" % (
                addr))

        # Figure out what data the address point to
        dataAddr = int(addr[2:], 16)
        self.regOffset = 0x7F & dataAddr

        # Figure out what axis we are looking at
        mBaseAddr = dataAddr & 0xFFF80
        try:
            self.axisNo = motorBaseAddrs.index(mBaseAddr) + 1
        except:
            log.error("#### Error: could not recognise motor base address: %X" % (
                mBaseAddr))

        # Get the data source info (unit, scaling algorithm and so on)
        for dataSrc in dataSources:
            if dataSrc['reg'] == self.regOffset:
                self.dataSourceInfo = dataSrc
                break
        if not self.dataSourceInfo:
            log.error(
                "### Error: could not recognise data source type with reg "
                "offset: %X" % (
                    self.regOffset))

        return

    # Receive the array of strings straight from the source
    def setStrData(self, strData):
        self.strData = strData
        return

    # Convert the array of hexadecimal strings to int or float arrays
    def strToRaw(self):
        # if we have no data yet, return with error
        if not (len(self.strData) > 0):
            return False

        # Check the data width to be able to make a proper conversion
        # from string to signed integer/float
        if self.dataWidth == LONGWORD:
            signMask = 0x800000000000
            maxValue = 0xFFFFFFFFFFFF
        elif self.dataWidth == WORD:
            signMask = 0x800000
            maxValue = 0xFFFFFF
        else:
            log.error("### Error: did not have valid data width "
                  "information (had %d)" % self.dataWidth)
            return None

        # convert each hex string value to an integer with sign
        self.rawData = []
        for strDataPoint in self.strData:
            val = int(strDataPoint, 16)
            if val & signMask:
                val -= maxValue
            self.rawData.append(val)
        return

    def getScalingFactor(self):
        # if a scaling algorithm doesn't exist we just set scaling factor to 1
        if 'scalingCalc' not in self.dataSourceInfo:
            self.scalingFactor = 1.0
            return

        # Get the necessary I variable factors from the pmac
        ivarFactors = []
        retStr = None
        status, retries = False, 2  # fails 1st attempt after the gather ??
        for partIvar in self.dataSourceInfo['scalingIvars']:
            ivar = partIvar % self.axisNo
            while retries > 0 and not status:
                (retStr, status) = self.pmac.sendCommand(ivar)
            if not status:
                log.error("### Error: did not receive response to: %s" % ivar)
                return None
            # if hex value...
            if retStr[0] == '$':
                ivarFactor = int(retStr.strip('$'), 16)
            else:
                ivarFactor = float(retStr[:-1])
            ivarFactors.append(ivarFactor)

        # calculate the final scaling factor from the ivar factors
        # and the algorithm as described in the pmac manual
        ivarFactors = tuple(ivarFactors)
        algorithm = self.dataSourceInfo['scalingCalc'] % ivarFactors
        # log.error "Evaluating algorithm: %s"%( algorithm )
        try:
            self.scalingFactor = eval(algorithm)
        except:
            log.error(
                "### Error: did not evaluate expression correctly. Expr: %s" % (
                    algorithm))
            return None

        return

    def rawToScaled(self):
        if not self.scalingFactor:
            self.getScalingFactor()
        if not self.rawData:
            log.error("### Error: No raw data available to scale.")
            return None
        if not self.scalingFactor:
            self.scaledData = self.rawData
            return None

        self.scaledData = []
        for rawVal in self.rawData:
            self.scaledData.append(rawVal * self.scalingFactor)
        return

# \file
# \section License
# Author: Diamond Light Source, Copyright 2011
#
# 'dls_pmaccontrol' is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'dls_pmaccontrol' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with 'dls_pmaccontrol'.  If not, see http://www.gnu.org/licenses/.
