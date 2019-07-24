from time import sleep
from datetime import datetime, timedelta
from .gatherchannel import dataSources, motorBaseAddrs, GatherChannel, WORD, \
    LONGWORD

BRICK_CLOCK = 5000  # servo loop speed in Hz

class PmacGather:
    """
    Initiates a pmac gather and collects the results. Independent of GUI but
    relies on a dls_pmaclib.RemotePmacInterface for communicating with the
    brick
    """
    def __init__(self, pmac_remote):
        self.pmac = pmac_remote
        self.channels = []
        self.no_of_words = 0
        self.samples = 0
        self.sample_time = 0
        self.start_time = datetime.now()

    def gatherConfig(self, axis_list, samples, sample_time):
        self.samples = samples
        self.sample_time = sample_time

        # set up i5050 with the necessary bit mask for n (no. of axes) channels
        dataSource = 0  # desired position
        axis_bits = 0
        for a in range(len(axis_list)):
            axis_bits |= (0x01 << a)

        if axis_bits == 0:
            return False

        cmd = "i5051=0 i5050=$%x" % axis_bits
        self.pmac.sendCommand(cmd)

        # set sample time
        self.pmac.sendCommand("i5049=%d" % sample_time)

        total_width = 0
        # set up each channel to gather demand position for the listed axes
        for index, axis in enumerate(axis_list):
            dataOffset = dataSources[dataSource]['reg']
            baseAddress = motorBaseAddrs[axis - 1]
            dataWidth = dataSources[dataSource]['size']
            ivar = "i50%02d" % (index + 1)
            addr = "$%X%05X" % (dataWidth, baseAddress + dataOffset)
            cmd = "%s=%s" % (ivar, addr)
            self.pmac.sendCommand(cmd)

            new_channel = GatherChannel(self.pmac)
            self.channels.append(new_channel)

            new_channel.setDataGatherPointer(ivar)

            new_channel.getDataInfo(addr)
            total_width += new_channel.dataWidth

        # set up the gather buffer of correct size
        self.no_of_words = int(total_width / WORD)
        # readWords needs an extra word if no_of_words is odd
        readWords = self.no_of_words + self.no_of_words % 2

        gatherBufSize = 47 + ((readWords / 2) * samples)
        cmd = "define gather %d" % gatherBufSize
        self.pmac.sendCommand(cmd)

    def gatherWait(self):
        wait_time = self.samples / (BRICK_CLOCK/self.sample_time)
        sleep_delta = wait_time - (datetime.now() - self.start_time).seconds
        if sleep_delta > 0:
            sleep(sleep_delta)

    def gatherTrigger(self, wait=True):
        self.start_time = datetime.now()
        self.pmac.sendCommand("gather")
        if wait:
            self.gatherWait()

    def collectData(self):
        (retStr, status) = self.pmac.sendCommand("list gather")
        lstDataStrings = []
        if status:
            # lstDataStrings = retStr[:-1].split()
            for long_val in retStr[:-1].split():
                lstDataStrings.append(long_val.strip()[6:])
                lstDataStrings.append(long_val.strip()[:6])
        else:
            error = "Problem retrieving gather buffer, status: {} " \
                " returned data: {}".format(status, retStr)
            error += "\nNOTE: make sure no other software is polling the brick"
            raise ValueError(error)

        return lstDataStrings

    def parseData(self, lstDataStrings):
        channel_count = len(self.channels)
        lstDataArrays = list([] for _ in range(channel_count))

        channel = 0
        tmpLongVal = None

        for strVal in lstDataStrings:
            if channel >= channel_count:
                channel = 0
                if self.no_of_words % 2 == 1:
                    # Read a dummy word since an uneven number of words
                    # causes the pmac to send a random word at the end of a
                    # line...
                    continue

            if self.channels[channel].dataWidth == WORD:
                lstDataArrays[channel].append(strVal)
                channel += 1
                continue
            if self.channels[channel].dataWidth == LONGWORD:
                if not tmpLongVal:
                    tmpLongVal = strVal
                else:
                    lstDataArrays[channel].append(strVal + tmpLongVal)
                    tmpLongVal = None
                    channel += 1
                continue

        for chIndex, ch in enumerate(self.channels):
            ch.setStrData(lstDataArrays[chIndex])
            ch.strToRaw()
            ch.rawToScaled()
