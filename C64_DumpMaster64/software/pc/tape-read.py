#!/usr/bin/env python3
# ===================================================================================
# Project:   DumpMaster64 - Python Script - Read Tape Image to TAP File
# Version:   v1.3
# Year:      2022
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   http://creativecommons.org/licenses/by-sa/3.0/
# ===================================================================================
#
# Description:
# ------------
# Reads a tape image from Datasette to TAP file
#
# Dependencies:
# -------------
# - adapter (included in libs folder)
#
# Operating Instructions:
# -----------------------
# - Set the selector switch on your DumpMaster64 adapter to "UART"
# - Connect the adapter to your Commodore Datasette
# - Connect the adapter to a USB port of your PC
# - Execute this skript: python tape-read.py outputfile.tap
# - Press PLAY on your Datasette when prompted
# - The dumping is done fully automatically. It stops when the end of the cassette
#   is reached, when there are no more signals on the tape for a certain time or
#   when the STOP button on the Datasette is pressed.


import sys
import time
from libs.adapter import *


# Print Header
print('')
print('--------------------------------------------------')
print('DumpMaster64 - Python Command Line Interface v1.3')
print('(C) 2022 by Stefan Wagner - github.com/wagiminator')
print('--------------------------------------------------')


# Get and check command line arguments
try:
    fileName = sys.argv[1]
except:
    raise AdpError('Missing output file name')


# Establish serial connection
print('Connecting to DumpMaster64 ...')
dumpmaster = Adapter()
if not dumpmaster.is_open:
    raise AdpError('Adapter not found')
print('Adapter found on port', dumpmaster.port)
print('Firmware version:', dumpmaster.getversion())
print('')


# Open output file
print('Opening', fileName, 'for writing ...')
try:
    f = open(fileName, 'wb')
except:
    dumpmaster.close()
    raise AdpError('Failed to open ' + filename)


# Write TAP file header
f.write(b'C64-TAPE-RAW\x01\x00\x00\x00\x00\x00\x00\x00')


# Send read command to DumpMaster64 and wait for PLAY pressed
print('PRESS PLAY ON TAPE')
dumpmaster.sendcommand(CMD_READTAPE)
while 1:
    data = dumpmaster.read(1)
    if data:
        break
    sys.stdout.write('#')
    sys.stdout.flush()
print('\r', ' ' * 50, end='\r')
if data[0] > 0:
    f.close()
    dumpmaster.close()
    raise AdpError('Timeout waiting for PLAY')
else:
    print('OK')
    print('Searching ...')


# Receive data from DumpMaster64 and write to output file
count     = 0
fsize     = 0
checksum  = 0
minpulse  = 65535
maxpulse  = 0
taptime   = 0
startflag = 0
starttime = time.time()
msgtime   = time.time()

while 1:
    data = dumpmaster.read(2)
    if data:
        dataval = int.from_bytes(data, byteorder='little')
        if dataval == 0:
            break
        if startflag == 0 and dataval > 32 and dataval < 64:
            print('Loading ...')
            startflag = 1
        if startflag == 1:
            if dataval > 255:
                f.write(b'\x00')
                f.write((dataval * 8).to_bytes(3, byteorder='little'))
                fsize += 4
            else:
                f.write(bytes([dataval]))
                fsize += 1
                if dataval > 16 and dataval < 128:
                    count += 1
                    minpulse  = min(minpulse, dataval)
                    maxpulse  = max(maxpulse, dataval)
                    if time.time() - msgtime > 0.5:
                        sys.stdout.write('\rPulses: ' + str(count))
                        msgtime = time.time()
            taptime += dataval
        checksum += data[0]
        checksum += data[1]
        checksum %= 65536

duration = round(time.time() - starttime)
taptime  = taptime * 8 // 1000000 + 1

f.seek(16)
f.write(fsize.to_bytes(4, byteorder='little'))
testsum  = int.from_bytes(dumpmaster.read(2), byteorder='little')
overflow = dumpmaster.read(1)[0]
print(' ' * 50, end='\r')


# Close output file and serial connection
f.close()
dumpmaster.close()


# Validate data and checksum, print infos, exit
if count == 0:
    raise AdpError('Timeout waiting for pulses')

print('Dumping finished')
print('---------------------------------------------------------')
print('Total pulses:      ', count)
print('Min pulse length:  ', minpulse)
print('Max pulse length:  ', maxpulse)
print('Total TAP time:    ', taptime//60, 'min', taptime%60, 'sec')
print('Transfer duration: ', duration//60, 'min', duration%60, 'sec')

errors = 0
if overflow == 0:
    print('Buffer status:     ', 'OK')
else:
    print('Buffer status:     ', 'OVERFLOW ERROR')
    errors = 1
if checksum == testsum:
    print('Checksum:          ', 'OK')
else:
    print('Checksum:          ', 'MISMATCH ERROR')
    errors = 1

print('---------------------------------------------------------')

if errors > 0:
    raise AdpError('Dumping failed')
print('Dumping successful')
print('')
sys.exit(0)
