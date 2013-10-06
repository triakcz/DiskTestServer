#!/usr/bin/python
# -*- encoding: utf-8 -*-
"""
disktester - coordinator of disk testing
Copyright (C) 2013 Ondřej Kunc

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from SimpleXMLRPCServer import SimpleXMLRPCServer
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
import threading
import subprocess
import sys
import select
import re
import os

# Create server
server = SimpleXMLRPCServer(("localhost", 9595),allow_none=True)
server.register_introspection_functions()

# Register an instance; all the methods of the instance are
# published as XML-RPC methods (in this case, just 'div').

class ExternalCommandThread(threading.Thread):
    def __init__(self,server,command,env=None):
        threading.Thread.__init__(self,name=" ".join(command));
        self.server=server
        self.command=command
        self.out=""
        self.oute=""
        self.env=env
    def run(self):
        self.subprocess=subprocess.Popen(self.command,stdout=subprocess.PIPE, stderr=subprocess.PIPE,env=self.env)
        stdout = []
        stderr = []

        retval=None

        while True:
            reads = [self.subprocess.stdout.fileno(), self.subprocess.stderr.fileno()]
            ret = select.select(reads, [], [])

            for fd in ret[0]:
                if fd == self.subprocess.stdout.fileno():
                    read = self.subprocess.stdout.read(1)
                    if read in ['\x08','\x10','\x13']:
                        self.out=self.out.trim()
                        if self.out:
                            self.readStdout(strip(self.out))
                        self.out=""
                    else:
                        self.out+=read
                    stdout.append(read)
                if fd == self.subprocess.stderr.fileno():
                    read = self.subprocess.stderr.read(1)
                    if read in ['\x08','\x10','\x13']:
                        self.oute=self.oute.strip()
                        if self.oute:
                            self.readStderr(self.oute)
                        self.oute=""
                    else:
                        self.oute+=read
                    stderr.append(read)
            retval=self.subprocess.poll()
            if retval != None:
                break

        (o,e)=self.subprocess.communicate()
        for i in o.split('\n'):
            self.readStdout(i)

        for i in e.split('\n'):
            self.readStderr(i)

        self.finish(retval,("".join(stdout))+o,("".join(stderr))+e)

    def readStdout(self,stdout):
        pass

    def readStderr(self,stderr):
        pass

    def finish(self,retval,stdout,stderr):
        pass

class RunBadblocksThread(ExternalCommandThread):
    def __init__(self,server,disk):
        self.disk=disk
        command=["stdbuf","-i0","-e0","-o0","/sbin/badblocks","-wsve1",disk]
        env=os.environ.copy()
        env['LANG']='C'
        ExternalCommandThread.__init__(self,server,command,env)

    def readStderr(self,stderr):
        print "STDERR:",stderr,"\n"

    def readStdout(self,stdout):
        print "STDOUT:",stdout,"\n"

    def finish(self,retval,stdout,stderr):
        print retval,stdout,stderr

class GetDriveSmartTableThread(ExternalCommandThread):
    def __init__(self,server,disk):
        self.disk=disk
        command=["/usr/sbin/smartctl","-a",disk]
        ExternalCommandThread.__init__(self,server,command)

    def finish(self,retval,stdout,stderr):
        d={'serial':None,'capacity':None,'model':None}
        for l in stdout.split('\n'):
            m=re.search('^Serial Number:\s*(\S+)$',l)
            if m:
                d['serial']=m.group(1)
            m=re.search('^Device Model:\s*(.+)$',l)
            if m:
                d['model']=m.group(1)
            m=re.search('^User Capacity:.+bytes\s+\[(250 GB)\]$',l)
            if m:
                d['capacity']=m.group(1)
            m=re.match('^\s*\d+\s+(\w+)\s+0x\d+\s+\d+\s+\d+\s+\d+\s+\w+\s+\w+\s+\S+\s+(\d+)',l)
            if m:
                d[m.group(1)]=m.group(2)

        d['retval']=retval
        d['stderr']=stderr
        #d['stdout']=stdout

        self.server.disks[self.disk]=d

class DiskTester:
    def __init__(self):
        self.disks={}

    def getDisks(self):
        return self.disks

    def addDisk(self,devname,startTests=False):
        print "Start tests: %s"%startTests
        if startTests:
            x=RunBadblocksThread(self,devname)
            x.start()
        if not self.disks.has_key(devname):
            self.disks[devname]={}
            return True
        else:
            return False

    def startCommand(self):
        x=ExternalCommandThread(self,['sleep','50'])
        x.start()

    def getDriveSmart(self,drive):
        x=GetDriveSmartTableThread(self,drive)
        x.start()

    def getThreads(self):
        x=[]
        for i in threading.enumerate():
            x.append(i.name)
        return x
            


server.register_instance(DiskTester())

# Run the server's main loop
server.serve_forever()
