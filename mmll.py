#!/usr/bin/python

'''
mmll.py
- the Most Minimal Linux Logger

Copyright 2013 Ted Richardson.
Distributed under the terms of the GNU General Public License (GPL)
See LICENSE.txt for licensing information.

usage: mmll.py [-h] -c CONFIGFILE [-o OUTPUTFILE] [-d {0,1,2,3,4}]

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIGFILE, --configfile CONFIGFILE
                        The logging config file
  -o OUTPUTFILE, --outputfile OUTPUTFILE
                        The desired output log file - No entry outputs log
                        data to STDOUT
  -d {0,1,2,3,4}, --debug {0,1,2,3,4}
                        Increase the Debug Level (experimental)

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
import sys, time, argparse
import pylibme7
from pylibme7 import hexlist
from me7lconfig import *

debug = 0   # Default debug value.  Can be overridden from the command line.

def printconfig(config):
   # Print out the config info
   print("Note:  Only using Connect, and Logspeed so far.")  
   print("       Connect must only be 'SLOW-0x11' and not all baud rates are supported yet")
   print("       Sample Rate is ignored once max logging speed is achieved.")
   print()
   print("From Config Files:")
   print("ECU File     : " + config[0][0] )
   print("Sample Rate  : " + config[0][1] )
   print("ME7L Cfg Ver : " + config[0][2] ) 
   print("Connect      : " + config[0][3] ) 
   print("Communicate  : " + config[0][4] )
   print("LogSpeed     : " + config[0][5] )
   print("HWNumber     : " + config[0][6] )
   print("SWNumber     : " + config[0][7] )
   print("PartNumber   : " + config[0][8] )
   print("SWVersion    : " + config[0][9] )
   print("EngineID     : " + config[0][10] )

def textlist(tl):
   # Outputs a list of bytes as a string of the corresponding ASCII characters.
   debugneeds = 4
   textresponse = ""
   for i in range(len(tl)-4):
      textresponse = textresponse + chr(tl[i+3])
   if debug >= debugneeds: print( "textlist() response: " + textresponse )
   return textresponse
 
def parselogdata(config, logdata, starttime):
   # Takes the raw logged values and applies the conversions from the ECU config file.
   logline = (str( round((time.time() - starttime),3) ).ljust(4,'0')).rjust(10) + ', '
   counter = logdata.index( 0xF7 ) + 1
   for l in range(1,len(config)):
      size = int(config[l][3])
      bitmask = int(config[l][4],16)
      s = bool(int(config[l][6]))
      i = bool(int(config[l][7]))
      a = float(config[l][8])
      b = float(config[l][9])
      
      bytes = logdata[ counter : counter + size ]
      byteconv = ""
      # Read bytes in reverse order.
      for j in range(len(bytes)):
         byteconv = hex(bytes[j])[2:].rjust(2,'0') + byteconv 
         internal = int('0x'+byteconv, 16)
      
      # bitmask code eeds tested
      if bitmask > 0:
         internal = internal & bitmask

      # signed/unsigned?
      if s == True:
         internal = signed(internal,size)

      # Inverse or regular?
      if i == False:
         endval = round((a * internal - b ),3)
      else:
         endval = round((a / (internal - b)),3)

      # Creates final line of logged data
      logline = logline + str(endval).rjust(10)
      if l < len(config)-1:
         logline = logline + ', '

      counter = counter + size
   return logline

def signed(n,bytecount):
      # Conversion for signed values
      conv = 2**((bytecount * 8) - 1)
      return ( n & (conv - 1 ) ) - ( n & conv ) 

def main(debug):
   # The main routine

   argparser = argparse.ArgumentParser()
   argparser.add_argument("-c", "--configfile", help="The logging config file", required=True)
   argparser.add_argument("-o", "--outputfile", help="The desired output log file - No entry outputs log data to STDOUT")
   argparser.add_argument("-d", "--debug", type=int, choices=[0, 1, 2, 3, 4], default=debug, help="Increase the Debug Level (experimental)")
   args = argparser.parse_args()


   try:
      # Use config data from the command line
      config = parseconfigfile(str(args.configfile))
      if str(args.outputfile) != "None":
         outfile = open(str(args.outputfile), 'w')
      else:
         outfile = sys.stdout
      debug = args.debug

      # Print Config data
      print()
      printconfig(config)

      print("...signed")


      ecu = pylibme7.Ecu()
      ecu.initialize(config[0][3])
      print(config)

      print("....sealed")

      # print("Connected at 14400")
      ecu.readecuid([0x91])
      # swnumber = textlist(response)
      swnumber = ""

      # login
      response = ecu.securityAccessL3()
      # response = ecu.securityAccessL1()
 
      response = ecu.startdiagsession(int(config[0][5]))
      # TODO: validate positive response
      if debug >= 3:  print("startdiagsession(" + config[0][5] +") response: " + hexlist(response) )
      print("Connected at " + config[0][5] )

      try:
         response = ecu.readecuid([0x87])
         hardwareNumber = textlist(response)
         print(f"VW Diagnosesoftwarenummer: {hardwareNumber}")
      except:
         pass
      try:
         response = ecu.readecuid([0x91])
         hardwareNumber = textlist(response)
         print(f"VW hardwareNumber: {hardwareNumber}")
      except:
         pass
      try:
         response = ecu.readecuid([0x9b])
         vwecuID = textlist(response)
         print(f"VW ECU ID: {vwecuID}")
      except:
         pass
      try:
         response = ecu.readecuid([0x9c])
         flashInfo = textlist(response)
         print(f"FlashInfo: str:{flashInfo} hex:{hexlist(response)}")
      except:
         pass


      p2min = [ 0 ]
      p2max = [ 1 ]
      p3min = [ 0 ]
      p3max = [ 20 ]
      p4min = [ 0 ]
      p4max = [ 20 ]
      accesstiming = p2min + p2max + p3min + p3max + p4min
      # response = ecu.accesstimingparameter(accesstiming)
      # if debug >= 3:  print("accesstimingparameter() response: " + hexlist(response) )
 
      print("Timing Set, reading and preparing memory")

      # I don't know how this is used.  Is it really ECU Scaling?

      # response = ecu.readecuid([ 0x94 ])
      swnumber = "textlist(response)"
      if debug >= 3:  print("SWNumber =" + swnumber)

      # response = ecu.readecuid([ 0x92 ])
      hwnumber = "textlist(response)"
      if debug >= 3:  print("HWNumber =" + hwnumber)

      # response = ecu.readecuid([ 0x9b ])
      partraw = "textlist(response)"
      if debug >= 3:  print("partraw  =" + partraw)
      partnumber = partraw[:12]
      swversion = partraw[12:16]
      engineid = partraw[26:42]
      modelid = partraw[42:]
      # Now that we know it, tacking ModelId on the end of the ecu config info
      config[0] = config [0] + [ modelid ]

      #I don't know how this is used.
      ecuid_0x9c = ecu.readecuid([ 0x9c ])
      if debug >= 3:  print("exuid_0x9c =" + hexlist(ecuid_0x9c) )

      # Check ECU values versus config file
      cfgcheck = True
      sys.stdout.write("Checking HWNumber   - config:[" + config[0][6].ljust(10) + "]       ecu:[" + hwnumber.ljust(10) + ']       : ')
      if config[0][6] != hwnumber:
         sys.stdout.write("FAIL" + '\n')
         cfgcheck = False
      else:
         sys.stdout.write("pass" + '\n')

      sys.stdout.write("Checking SWNumber   - config:[" + config[0][7].ljust(10) + "]       ecu:[" + swnumber.ljust(10) + ']       : ')
      if config[0][7] != swnumber:
         sys.stdout.write("FAIL" + '\n')
         cfgcheck = False
      else:
         sys.stdout.write("pass" + '\n')

      sys.stdout.write("Checking Partnumber - config:[" + config[0][8].ljust(12) + "]     ecu:[" + partnumber.ljust(12) + ']     : ')
      if config[0][8] != partnumber:
         sys.stdout.write("FAIL" + '\n')
         cfgcheck = False
      else:
         sys.stdout.write("pass" + '\n')

      sys.stdout.write("Checking SWVersion  - config:[" + config[0][9].ljust(4) + "]             ecu:[" + swversion.ljust(4) + ']             : ')
      if config[0][9] != swversion:
         sys.stdout.write("FAIL" + '\n')
         cfgcheck = False
      else:
         sys.stdout.write("pass" + '\n')

      sys.stdout.write("Checking EngineId   - config:[" + config[0][10].ljust(16) + "] ecu:[" + engineid.ljust(16) + '] : ')
      if config[0][10] != engineid:
         sys.stdout.write("FAIL" + '\n')
         cfgcheck = False
      else:
         sys.stdout.write("pass" + '\n')

      sys.stdout.write("Displaying ModelId  -                           ecu:[" + modelid + ']' + '\n')

      #TODO: edc16 doesnt poll the same
      cfgcheck = True

      if cfgcheck == True:

         response = ecu.testerpresent()
         if debug >= 3:  print("testerpresent(): response: " + hexlist(response))

         ecu.send( [ 0x00 ] )                          # Why is this extra 0x00 needed?
         ecu.recv(1)   

         # Tell ECU memory locations to log, based on the config and ecu file data:
         logline = loglocations(config)
         def setuplogrecord():
            return ecu.setuplogrecord(logline[0])
         success = False
         while(not success):
            try:
               response = ecu.setuplogrecord(logline[0])
               success = True
            except Exception as e:
               if e.args[0] != "busyRepeatRequest":
                  raise e
               print("retrying....");
               
         if debug >= 3:  print("loglocations(): request: " + hexlist(logline[0]) + " response: " + hexlist(response) )
         # grab logpacketsize from loglocations() return and tack it to the end of ecu config info
         config[0] = config[0] + [ logline[1] ]

         print(".....delivered")
         if str(args.outputfile) != 'None':
            sys.stdout.write("Logging (ctrl-c to end):  ")


         # Finally, start logging records!

         headers = logheader(config)
         for line in headers:
            outfile.write(line + '\n')

         secondstolog = 10
         starttime = time.time()

         spinner = 0
         spinstr = [ '|', '/', '-', '\\' ]

         while True:
            timerstart = time.time()
            response = ecu.getlogrecord()
            if debug >= 3:  print("getrecord(): request: [ 0xb7 ] response: " + hexlist(response))

            # Pipe log output to parser, based on info pulled from the config and ecu files
            response = parselogdata(config, response, starttime)
            outfile.write( response + '\n') 


            # Just for fun
            if str(args.outputfile) != 'None':
               spinout = spinstr[spinner]
               sys.stdout.write('\b' + spinout)
               sys.stdout.flush()
               spinner = spinner + 1
               if spinner == 4: spinner = 0

            # Sleep to adjust log records per second
            samplerate = 1/int(config[0][1])
            timerfinish = time.time()
            adjust = (timerfinish-timerstart)
            if adjust < samplerate:
               time.sleep((samplerate)-(timerfinish-timerstart))

      else:
         print("Config check failed")

   # Catch ctrl-c
   except KeyboardInterrupt:
      sys.stdout.write('\r' + "Stopping".ljust(30) + '\n')

   sys.stdout.write('\r')
   sys.stdout.flush()
   
   # Wrap things up.
   outfile.flush()
   print("Logging Finished")


   
if __name__ == '__main__':

   try:
     main(debug)

   except KeyboardInterrupt:
     print("hard stop")

