#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# async - A tool to manage and sync different machines
# Copyright 2013 Abdó Roig-Maranges <abdo.roig@gmail.com>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import sys
import time
import shlex
import subprocess


if sys.version_info[0] < 3:
    def shquote(s):
        return "'" + s.replace("'", "'\"'\"'") + "'"
else:
    shquote = shlex.quote


class SSHConnectionError(Exception):
    def __init__(self, msg=None):
        super(SSHConnectionError, self).__init__(msg)

class SSHCmdError(Exception):
    def __init__(self, msg=None, returncode=None, output=""):
        super(SSHCmdError, self).__init__(msg)
        self.output = output
        self.returncode = returncode


class SSHConnection(object):
    """A ssh connection through a socket"""

    def __init__(self, socket):

        self.socket = os.path.expanduser(socket)
        self.master_proc = None
        self.decorated_host = None
        self.args = []


    def __del__(self):
        self.close()



    def _ssh(self, args, timeout=30, stdout=None, stderr=None, stdin=None):
        sshargs = ['-o', 'ConnectTimeout=%s' % str(timeout)]
        sshargs = sshargs + args
        try:
            proc = subprocess.Popen(['ssh'] + sshargs,
                                    stdout=stdout, stderr=stderr, stdin=stdin)

        except subprocess.CalledProcessError as err:
            raise SSHConnectionError(str(err))

        return proc


    def _parse_ssh_config(self, path):
        hosts = {}

        if not os.path.exists(path):
            return hosts

        with open(path, 'r') as fd:
            raw = fd.read()

        for rawhost in re.split("^\s*Host\s", raw, flags=re.MULTILINE):
            rawhost = rawhost.strip()
            if len(rawhost) == 0: continue

            Lh = rawhost.split('\n')
            if len(Lh) > 0:
                names = [n.strip() for n in Lh[0].split()]

                dic = {}
                for line in Lh[1:]:
                    m = re.match("^\s*([^\s]*)\s(.*)$", line)
                    if m:
                        dic[m.group(1).strip()] = m.group(2).strip()

                for nm in names:
                    hosts[nm.strip()] = dic

        return hosts


    def resolve(self, hostname):
        """Resolves a hostname into a tuple, (fqdn, ip). Parses .ssh/config to resolve
        aliases."""

        hosts = self._parse_ssh_config(os.path.expanduser("~/.ssh/config"))

        if hostname in hosts:
            dic = hosts[hostname]
            if "HostName" in dic: hostname = dic['HostName']

        raw = subprocess.check_output(['host', '-4', hostname])
        m = re.match("^(.*) has address (\d+.\d+.\d+.\d+)\s*$", raw)
        if m:
            return (m.group(1).strip(), m.group(2).strip())

        else:
            if re.match("^(\d+.\d+.\d+.\d+)$", hostname): return (None, hostname)
            else:                                         return (None, None)


    def connect(self, hostname, user=None, keyfile=None, timeout=30, args=[]):
        self.args = []
        if keyfile: self.args = self.args + ['-i', keyfile]
        self.args = self.args + args

        if user: self.decorated_host = "%s@%s" % (user, hostname)
        else:    self.decorated_host = hostname

        if os.path.exists(self.socket):
            raise SSHConnectionError("Socket %s already exists" % self.socket)

        sshargs = ['-M', '-N', '-o', 'ControlPath=%s' % self.socket] + self.args
        with open('/dev/null', 'w') as devnull:
            self.master_proc = self._ssh(sshargs + [self.decorated_host],
                                         timeout=timeout, stdout=devnull, stderr=devnull)

        sec = 0
        while not self.alive() and sec <= timeout:
            time.sleep(1)
            sec = sec + 1

        if sec >= timeout:
            raise SSHConnectionError("Can't connect: timeout")



    def run(self, cmd, args=[], timeout=30, catchout=False, stdin=None):
        sshargs = ['-o', 'ControlPath=%s' % self.socket] + self.args + args
        qcmd = 'sh -c %s' % shquote(cmd)

        if self.decorated_host == None:
            raise SSHConnectionError("Not authenticated")

        stdi = stdo = stde = None
        if catchout:
            stdo = subprocess.PIPE
            stde = subprocess.STDOUT

        if stdin != None:      stdi = subprocess.PIPE
        else:                  stdi = None

        proc = self._ssh(sshargs + [self.decorated_host, qcmd],
                         timeout=timeout,
                         stdout=stdo, stderr=stde, stdin=stdi)

        # stderr is piped to stdout
        stdout, stderr = proc.communicate(stdin)

        if proc.returncode != 0:
            raise SSHCmdError("SSH command failed: %s" % cmd, proc.returncode, stdout)

        if catchout: return stdout
        else:        return None

    def close(self):
        if os.path.exists(self.socket):
            # with open('/dev/null', 'w') as devnull:
            #    proc = self._ssh(['-S', self.socket, '-O', 'exit', self.decorated_host])
            #    ret = proc.wait()
            #    if ret != 0:
            #        raise SSHConnectionError("Error disconnecting socket %s" % self.socket)

            if self.master_proc:
                self.master_proc.terminate()
                self.master_proc = None
                self.decorated_host = None



    def alive(self, timeout=30):
        try:
            alive = os.path.exists(self.socket) and \
                    self.master_proc and \
                    self.master_proc.poll() == None
                    # and self.run('true', timeout=timeout) == 0
            return alive

        except:
            return False
