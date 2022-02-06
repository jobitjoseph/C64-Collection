#!/usr/bin/env python3
# ===================================================================================
# Project:   DiskBuddy64 - Python Script - Write Disk Image from D64 File
# Version:   v1.3
# Year:      2022
# Author:    Stefan Wagner
# Github:    https://github.com/wagiminator
# License:   http://creativecommons.org/licenses/by-sa/3.0/
# ===================================================================================
#
# Description:
# ------------
# Writes disk image from D64 file
#
# Dependencies:
# -------------
# - adapter (included in libs folder)
# - disktools (included in libs folder)
#
# Operating Instructions:
# -----------------------
# - Set the serial mode switch on your DiskBuddy64 adapter to "UART"
# - Connect the adapter to your floppy disk drive(s)
# - Connect the adapter to a USB port of your PC
# - Switch on your floppy disk drive(s)
# - Execute this skript:
#
# - python disk-write.py [-h] [-b] [-d {8,9,10,11}] [-i INTER] -f FILE
#   optional arguments:
#   -h, --help                    show help message and exit
#   -b, --bamonly                 only write blocks with BAM entry (recommended)
#   -d, --device                  device number of disk drive (8-11, default=8)
#   -i INTER, --interleave INTER  sector interleave (default=4)
#   -f FILE,  --file FILE         input file (*.d64)
#
# - Example: python disk-write.py -b -f game.d64


import sys
import os
import time
import argparse
from libs.adapter import *
from libs.disktools import *


# Constants and variables
FASTWRITE_BIN = 'libs/fastwrite.bin'
tracks = 35


# Print Header
print('')
print('--------------------------------------------------')
print('DiskBuddy64 - Python Command Line Interface v1.3')
print('(C) 2022 by Stefan Wagner - github.com/wagiminator')
print('--------------------------------------------------')


# Get and check command line arguments
parser = argparse.ArgumentParser(description='Simple command line interface for DiskBuddy64')
parser.add_argument('-b', '--bamonly', action='store_true', help='only write blocks with BAM entry (recommended)')
parser.add_argument('-d', '--device', choices={8, 9, 10, 11}, type=int, default=8, help='device number of disk drive (default=8)')
parser.add_argument('-i', '--interleave', type=int, default=4, help='sector interleave (default=4)')
parser.add_argument('-f', '--file', required=True, help='input file (*.d64)')

args = parser.parse_args(sys.argv[1:])
bamcopy    = args.bamonly
device     = args.device
filename   = args.file
interleave = args.interleave
if interleave < 1 or interleave > 17: interleave = 4


# Establish serial connection
print('Connecting to DiskBuddy64 ...')
diskbuddy = Adapter()
if not diskbuddy.is_open:
    raise AdpError('Adapter not found')
print('Adapter found on port:', diskbuddy.port)
print('Firmware version:', diskbuddy.getversion())


# Check if IEC device ist present and supported
magic = diskbuddy.detectdevice(device)
if not device_is_known(magic): 
    diskbuddy.close()
    raise AdpError('IEC device ' + str(device) + ' not found')
print('IEC device', device, 'found:', IEC_DEVICES[magic])
if not device_is_supported(magic):
    diskbuddy.close()
    raise AdpError(IEC_DEVICES[magic] + ' is not supported')


# Upload fast writer to disk drive RAM
print('Uploading fast writer ...')
if diskbuddy.uploadbin(FASTWRITE_LOADADDR, FASTWRITE_BIN) > 0:
    diskbuddy.close()
    raise AdpError('Failed to upload fast writer')


# Open input file
print('Opening', filename, 'for reading ...')
try:
    filesize = os.stat(filename).st_size
    f = open(filename, 'rb')
except:
    diskbuddy.close()
    raise AdpError('Failed to open ' + filename)


# Check input file
if not filesize == getfilepointer(tracks + 1, 0):
    if filesize == getfilepointer(41, 0):
        print('WARNING: This is a disk image with 40 tracks!')
        tracks = 40
    else:
        f.close()
        diskbuddy.close()
        raise AdpError('Wrong file size')


# Read BAM if necessary
print('')
if bamcopy:
    print('Reading BAM of input file ...')
    f.seek(getfilepointer(18, 0))
    fbam = BAM(f.read(256))


# Write disk
print('Writing disk ...')
starttime = time.time()
for track in range(1, tracks + 1):
    secnum  = getsectors(track)
    sectors = [x for x in range(secnum)]
    seclist = []

    # Cancel sectors without BAM entry
    if bamcopy and track < 36:
        for x in range(secnum):
            if fbam.blockisfree(track, x): sectors.remove(x)

    # Optimize order of sectors for speed
    sector  = 0
    counter = len(sectors)
    while counter:
        if sector >= secnum: sector -= secnum
        while not sector in sectors:
            sector += 1
            if sector >= secnum: sector = 0
        seclist.append(sector)
        sectors.remove(sector)
        sector  += interleave
        counter -= 1

    # Send command to disk drive, if there's something to write on track
    seclen = len(seclist)
    if seclen > 0:
        if diskbuddy.startfastwrite(track, seclist) > 0:
            f.close()
            diskbuddy.close()
            raise AdpError('Failed to start disk operation')

    # Write track
    trackline = ('Track ' + str(track) + ':').ljust(10) + '['
    sys.stdout.write(trackline + '-' * seclen + '0' * (secnum - seclen) + ']')
    sys.stdout.write('\r' + trackline)
    sys.stdout.flush()
    diskbuddy.timeout = 4
    for sector in seclist:
        f.seek(getfilepointer(track, sector))
        if diskbuddy.sendblockgcr(f.read(256)) > 0:
            print('')
            f.close()
            diskbuddy.close()
            raise AdpError('Failed to write sector to disk')
        sys.stdout.write('#')
        sys.stdout.flush()
    if seclen > 0:  diskbuddy.read(1);
    print('')

diskbuddy.executememory(MEMCMD_SETTRACK18)


# Finish all up
duration = time.time() - starttime
print('Done.')
print('Duration:', round(duration), 'seconds')
print('')
f.close()
diskbuddy.close()
