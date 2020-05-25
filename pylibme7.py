#!/usr/bin/python

'''
pylibme7
- a very basic python object for interacting with Bosch ME7 ECU's
- requires pylibftdi


Copyright 2013 Ted Richardson.
Distributed under the terms of the GNU General Public License (GPL)
See LICENSE.txt for licensing information.

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
--
trichard3000
'''

from __future__ import print_function, division
import sys
import time
import argparse
# This may need to be installed separately
from pylibftdi import Device, BitBangDevice

debug = 4

def hexlist(hexlist):
   result = ""
   for value in hexlist:
      result += '0x{0:0{1}X} '.format(value,2)
   return result

class Ecu:

    def __init__(self):
        self.ser = Device(mode='b', lazy_open=True)

    def slowInit11(self):
        # Take the one-byte address to "bit bang" and bang the port
        self.bbser = BitBangDevice()
        print("beginning slow init")
        self.bbser.open()
        self.bbser.direction = 0x01
        self.bbser.port = 1
        time.sleep(.5)
        self.bbser.port = 0
        time.sleep(.2)
        self.bbser.port = 1
        time.sleep(.2)
        self.bbser.port = 0
        time.sleep(1.4)
        self.bbser.port = 1
        time.sleep(.2)
        self.bbser.close()
        print("slow init sent")

    def initialize(self, connect):
        self.connect = connect
        if self.connect == "SLOW-0x11":
            self.ser.close()
            time.sleep(.5)

            self.ecuconnect = False
            while self.ecuconnect == False:
                print("Attempting ECU connect: " + self.connect)

                # Bit bang the K-line
                self.slowInit11()
                self.ser.open()
                self.ser.ftdi_fn.ftdi_set_line_property(8, 1, 0)
                self.ser.baudrate = 10400
                self.ser.flush()

                # Wait for ECU response to bit bang
                waithex = [0x55, 0xef, 0x8f, 1]
                print("Wating for init response")
                response = self.waitfor(waithex)
                print(f"Init response: {hexlist(response[2])}")
                # Wait a bit
                time.sleep(.026)

                # Send 0x70
                self.send([0x70])

                # 0xee means that we're talking to the ECU
                waithex = [0xfe, 1]
                print("waiting for ECU reponse")
                response = self.waitfor(waithex)
                print(f"ecu connection response: {hexlist(response[2])}")
                if response[0] == True:
                    self.ecuconnect = True
                else:
                    print("ECU Connect Failed.  Retrying.")
                    return
                print("INIT done")

    def waitfor(self, wf):
        # This was used for debugging and really is only used for the init at this point.
        # wf should be a list with the timeout in the last element
        self.wf = wf
        isfound = False
        idx = 0
        foundlist = []
        capturebytes = []
        to = self.wf[-1]
        timecheck = time.time()
        while (time.time() <= (timecheck+to)) & (isfound == False):
            try:
                recvbyte = self.recvraw(1)
                if recvbyte != b"":
                    recvdata = ord(recvbyte)
                    capturebytes = capturebytes + [recvdata]
                    if recvdata == self.wf[idx]:
                        foundlist = foundlist + [recvdata]
                        idx = idx + 1
                    else:
                        foundlist = []
                        idx = 0
                    if idx == len(self.wf)-1:
                        isfound = True
            except e:
                print([isfound, foundlist, capturebytes])
                print('error', e)
                break
        return [isfound, foundlist, capturebytes]

    def send(self, sendlist):
        self.sendlist = sendlist
        # Puts every byte in the sendlist out the serial port
        for i in self.sendlist:
            self.ser.write(chr(i))

    def recvraw(self, bytes):
        self.bytes = bytes
        recvdata = self.ser.read(self.bytes)
        return recvdata

    def recv(self, bytes):
        self.bytes = bytes
        isread = False
        while isread == False:
            recvbyte = self.ser.read(self.bytes)
            if recvbyte != b"":
                recvdata = recvbyte
                isread = True
        return recvdata

    def sendcommand(self, sendlist):
        # Wraps raw KWP command in a length byte and a checksum byte and hands it to send()
        self.sendlist = sendlist
        csum = 0
        self.sendlist = [len(self.sendlist)] + self.sendlist
        csum = self.checksum(self.sendlist)
        self.sendlist = self.sendlist + [csum]
        self.send(self.sendlist)
        print(f"sendcommand() sent: {hexlist(self.sendlist)}")
        cmdval = self.commandvalidate(self.sendlist)
        return cmdval

    def commandvalidate(self, command):
        # Every KWP command is echoed back.  This clears out these bytes.
        self.command = command
        cv = True
        for i in range(len(self.command)):
            recvdata = self.recv(1)
            if ord(recvdata) != self.command[i]:
                cv = cv & False
        return cv

    def checksum(self, checklist):
        # Calculates the simple checksum for the KWP command bytes.
        self.checklist = checklist
        csum = 0
        for i in self.checklist:
            csum = csum + i
        csum = (csum & 0xFF) % 0xFF
        return csum
    # used exclusivly for the errorhandling section
    def _raise(self,ex):
        raise ex
    def getresponse(self):
        # gets a properly formated KWP response from a command and returns the data.
        debugneeds = 4
        numbytes = 0
        # This is a hack because sometimes responses have leading 0x00's.  Why?  This removes them.
        while numbytes == 0:
            numbytes = ord(self.recv(1))
        gr = [numbytes]
        if debug >= debugneeds:
            print("Get bytes: " + hex(numbytes))
        for i in range(numbytes):
            recvdata = ord(self.recv(1))
            if debug >= debugneeds:
                print("Get byte" + str(i) + ": " + hex(recvdata))
            gr = gr + [recvdata]
        checkbyte = self.recv(1)
        if debug >= debugneeds:
            print(f"getresponse recieved: {hexlist(gr)}")
        if debug >= debugneeds:
            print("GR: " + hex(ord(checkbyte)) +
                  "<-->" + hex(self.checksum(gr)))
        if(gr[1]==0x7f):
            return { # returning the result so 0x78 (responsePending) can re-execute
                0x10: lambda: self._raise(Exception("generalReject", gr)),
                0x11: lambda: self._raise(Exception("busyRepeatRequest", gr)),
                0x12: lambda: self._raise(Exception("subFunctionNotSupported / invalidFormat",gr)),
                0x21: lambda: self._raise(Exception("busyRepeatRequest", gr)),
                0x22: lambda: self._raise(Exception("conditionsNotCorrectOrRequestSequenceError", gr)),
                0x23: lambda: self._raise(Exception("routineNotComplete", gr)),
                0x31: lambda: self._raise(Exception("requestOutOfRange", gr)),
                0x33: lambda: self._raise(Exception("securityAccessDenied / securityAccessRequested", gr)),
                0x35: lambda: self._raise(Exception("invalidKey", gr)),
                0x36: lambda: self._raise(Exception("exceedNumberOfAttempts", gr)),
                0x37: lambda: self._raise(Exception("requiredTimeDelayNotExpired", gr)),
                0x40: lambda: self._raise(Exception("downloadNotAccepted")),
                0x41: lambda: self._raise(Exception("improperDownloadType")),
                0x42: lambda: self._raise(Exception("canNotDownloadToSpecifiedAddress",gr)),
                0x43: lambda: self._raise(Exception("canNotDownloadNumberOfBytesRequested",gr)),
                0x50: lambda: self._raise(Exception("uploadNotAccepted",gr)),
                0x51: lambda: self._raise(Exception("improperUploadType",gr)),
                0x52: lambda: self._raise(Exception("canNotUploadFromSpecifiedAddress",gr)),
                0x53: lambda: self._raise(Exception("canNotUploadNumberOfBytesRequested",gr)),
                0x71: lambda: self._raise(Exception("transferSuspended",gr)),
                0x72: lambda: self._raise(Exception("transferAborted",gr)),
                0x74: lambda: self._raise(Exception("illegalAddressInBlockTransfer",gr)),
                0x75: lambda: self._raise(Exception("illegalByteCountInBlockTransfer",gr)),
                0x76: lambda: self._raise(Exception("illegalBlockTransferType",gr)),
                0x77: lambda: self._raise(Exception("blockTransferDataChecksumError",gr)),
                0x78: self.getresponse,
                0x79: lambda: self._raise(Exception("incorrectByteCountDuringBlockTransfer",gr)),
                0x80: lambda: self._raise(Exception("serviceNotSupportedInActiveDiagnosticMode",gr)),
                0x90: lambda: self._raise(Exception("noProgramm",gr)),
                0x91: lambda: self._raise(Exception("requiredTimeDelayNotExpired", gr))
            }.get(gr[3], lambda: self._raise( Exception("Generic KWP negative response", gr)))()
        return gr

    def readecuid(self, paramdef):
        #KWP2000 command to pull the ECU ID
        self.paramdef = paramdef
        debugneeds = 3
        response = self.sendcommand([0x10, 0x85]) # setup diag session
        reqserviceid = [0x1A]
        sendlist = reqserviceid + self.paramdef
        if debug >= debugneeds:
            print(f"readecuid sending: {hexlist(sendlist)}")
        self.sendcommand(sendlist)
        response = self.getresponse()
        if debug >= debugneeds:
            print(f"readecuid got: {hexlist(response)}")
        return response

    def securityAccessL3(self):
        ### Begin - level 3 security
        self.sendcommand([0x27,0x03])
        response = self.getresponse()
        print(f"Seed: {hexlist(response)}") 

        ## highBytes(uint8_t) = value(uint16_t) >> 8
        ## lowBytes(uint8_t) = value(uint16_t) & 0xff
        ## value(uint16_t) = (high << 8) + low

        seed = (response[3]<<24)+(response[4]<<16)+(response[5]<<8)+response[6]
        print(f"Seed: {seed}")

        key = seed + 12233 # standard VW access
        keyHex = [key >> 24 & 0xff, key >> 16 & 0xff, key >> 8 & 0xff, key & 0xff]
        print(f"Seed: {hexlist(keyHex)}")
        self.sendcommand([0x27, 0x04]+keyHex)
        try:
            response = self.getresponse() #sometimes this doesn't work
        except:
            response = self.getresponse()
        print(hexlist(response))
        if(response[3]!=0x34):
            raise Exception("failed to get L3 auth")

        print("End security level 3 access")
    # def securityAccessL1(self):
    #     pass
    #     ### Begin - Level 1 key/seed
    #     ## request seed 27 01
    #     self.sendcommand([0x27,0x01])
    #     response = self.getresponse()
    #     print(hexlist(response)) 
    #     # len? secreq  level    seed h    seed l    checksum
    #     # 0x06  0x67    0x01    0x6D 0x20 0xFC 0xB1   0xA8
    #     seedH = (response[3] << 8) + response[4]
    #     seedL = (response[5] << 8) + response[6]

    #     magicValue = 0x1c60020
    #     for count in range(5):
    #         tempstring = seedH &0x8000
    #         seedH = seedH << 1
    #         if(tempstring&0xFFFF == 0):
    #             temp2 = seedL&0xFFFF
    #             temp3 = tempstring&0xFFFF0000
    #             tempstring = temp2+temp3
    #             seedH = seedH&0xFFFE
    #             temp2 = tempstring&0xFFFF
    #             temp2 = temp2 >> 0x0F
    #             tempstring = tempstring&0xFFFF0000
    #             tempstring = tempstring+temp2
    #             seedH = seedH|tempstring
    #             seedL = seedL << 1
    #         else:
    #             tempstring = seedL+seedL
    #             seedH = seedH & 0xFFFE
    #             temp2 = tempstring & 0xFF #Same as EDC15 until this point
    #             temp3 = magicValue & 0xFFFFFF00
    #             temp2 = temp2 | 1
    #             magicValue = temp2 + temp3
    #             magicValue = magicValue & 0xFFFF00FF
    #             magicValue = magicValue | tempstring
    #             temp2 = seedL & 0xFFFF
    #             temp3 = tempstring & 0xFFFF0000
    #             temp2 = temp2 >> 0x0F
    #             tempstring = temp2 + temp3
    #             tempstring = tempstring | seedH
    #             magicValue = magicValue ^ 0x1289
    #             tempstring = tempstring ^ 0x0A22
    #             seedL = magicValue
    #             seedH = tempstring
    #     print(f"H:{seedH} L:{seedL}")
    #     ## high bytes = value >> 8
    #     ## low bytes = value & 0xff
    #     ## value = (high<<8) + low
    #     self.sendcommand([0x27,0x02, seedH & 0xff, seedH >>8, seedL & 0xff, seedL >> 8])
    #     # self.sendcommand([0x27,0x02, 0xff, 0xff, 0xff, 0xff])
    #     response = self.getresponse()

    def securityAccessL1(self):
        self.sendcommand([0x27,0x01])
        response = self.getresponse()
        print(hexlist(response))
        seed = (response[3]<<24)+(response[4]<<16)+(response[5]<<8)+response[6]
        print(f"L1 seed: {seed}")

        '''
        for (byte i = 0; i < 5; i++) {
            if ((seed & 0x80000000) == 0x80000000) { // Check carry
                seed = (SEED_DATA[ecuID]) ^ ((seed << 1) | (seed >>> 31)); // rotate left and xor
            }
            else {
                seed = ((seed << 1) | (seed >>> 31)); // rotate left only
            }
        }
        return seed;
        '''
        magicValue = 0x1c60020
        def rshift(val,n): return (val>>n) & (0x7fffffff>>(n-1))
        for x in range(5):
            if((seed & 0x80000000) == 0x80000000):
                seed = magicValue ^ ((seed<<1)|rshift(seed,31))
            else:
                seed =  ((seed<<1)|rshift(seed,31))
        print(f"L1 key: {seed}")
        keyHex = [seed >> 24 & 0xff, seed >> 16 & 0xff, seed >> 8 & 0xff, seed & 0xff]
        self.sendcommand([0x27,0x02]+keyHex)
        # self.sendcommand([0x27,0x02, 0xff, 0xff, 0xff, 0xff])
        return self.getresponse()

    def stopcomm(self):
        # KWP2000 command to tell the ECU that the communications is finished
        stopcommunication = [0x82]
        self.sendcommand(stopcommunication)
        response = self.getresponse()
        return response

    def startdiagsession(self, bps):
        # KWP2000 setup that sets the baud for the logging session
        self.bps = bps
        startdiagnosticsession = [0x10]
        sessionType = [0x86] 
    #   if self.bps == 10400:
    #      bpsout = [ 0x?? ]
    #   if self.bps == 14400:
    #      bpsout = [ 0x?? ]
        if self.bps == 19200:
            bpsout = [0x30]
        if self.bps == 38400:
            bpsout = [0x50]
        if self.bps == 56000:
            bpsout = [0x63]
        if self.bps == 57600:
            bpsout = [0x64]
        if self.bps == 124800:
            bpsout = [0x87]
        if self.bps == 250000:
            bpsout = [0xA7]
        if(self.bps != 0):
            sendlist = startdiagnosticsession + sessionType + bpsout
        else:
            sendlist = startdiagnosticsession + sessionType
        self.sendcommand(sendlist)
        response = self.getresponse()
        self.ser.baudrate = self.bps
        time.sleep(1)
        return response

    def accesstimingparameter(self, params):
        # KWP2000 command to access timing parameters
        self.params = params
        accesstiming_setval = [0x83, 0x03]
        accesstiming = accesstiming_setval + self.params
        sendlist = accesstiming
        self.sendcommand(sendlist)
        response = self.getresponse()
        return response

    def readmembyaddr(self, readvals):
        # Function to read an area of ECU memory.
        debugneeds = 4
        self.readvals = readvals
        rdmembyaddr = [0x23]
        sendlist = rdmembyaddr + self.readvals
        if debug >= debugneeds:
            print("readmembyaddr() sendlist: " + hexlist(sendlist))
        self.sendcommand(sendlist)
        response = self.getresponse()
        if debug >= debugneeds:
            print("readmembyaddr() response: " + hexlist(response))
        return response

    def writemembyaddr(self, writevals):
        # Function to write to an area of ECU memory.
        debugneeds = 4
        self.writevals = writevals
        wrmembyaddr = [0x3D]
        sendlist = wrmembyaddr + self.writevals
        if debug >= debugneeds:
            print("writemembyaddr() sendlist: " + hexlist(sendlist))
        self.sendcommand(sendlist)
        response = self.getresponse()
        if debug >= debugneeds:
            print("writemembyaddr() response: " + hexlist(response))
        return response

    def testerpresent(self):
        # KWP2000 TesterPresent command
        tp = [0x3E]
        self.sendcommand(tp)
        response = self.getresponse()
        return response

    def setuplogrecord(self, logline):
        # KWP2000 command to access timing parameters
        self.logline = logline
        response = []
        sendlist = [0xb7]                           # is 0xB7 the "locator?"
        sendlist = sendlist + [0x03]           # Number of bytes per field ?
        sendlist = sendlist + self.logline
        self.sendcommand(sendlist)
        response = self.getresponse()
        return response

    def getlogrecord(self):
        # Command to request a logging record
        gr = [0xb7]
        self.sendcommand(gr)
        response = self.getresponse()
        return response

    def sendhexstring(self, dumpstring):
        # Takes a list of characters as a string, turns every two characters into a hex byte and sends it raw.
        # used as needed for dev/test/debug
        self.dumpstring = dumpstring
        for i in range(len(self.dumpstring)/2):
            self.send([int('0x'+self.dumpstring[i*2:(i*2)+2], 16)])


def main():
    print("Loading pylibme7")


if __name__ == '__main__':

    try:
        main()

    except KeyboardInterrupt:
        print("hard stop")
