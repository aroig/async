#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# async - A tool to manage and sync different machines
# Copyright 2012,2013 Abdó Roig-Maranges <abdo.roig@gmail.com>
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

import re
import os
import sys
import subprocess

import async.archui as ui
import async.cmd as cmd

from async.hosts.base import BaseHost, HostError, CmdError
from async.openssh import SSHConnection, SSHConnectionError, SSHCmdError

class SshError(HostError):
    def __init__(self, msg=None):
        super(SshError, self).__init__(msg)


class SshHost(BaseHost):
    """A remote ssh host"""

    STATES = ['offline', 'running', 'online', 'mounted']

    def __init__(self, conf):
        ui.print_debug("begin SshHost.__init__")
        super(SshHost, self).__init__(conf)

        # ssh related config
        self.ssh_hostname     = conf['hostname']         # the hostname
        self.user             = conf['user']             # the user on the remote
        self.mac_address      = conf['mac_address']      # mac address
        self.ssh_key          = conf['ssh_key']          # the key for ssh connection
        self.ssh_trust        = conf['ssh_trust']

        self._hostname        = None
        self._ip              = None

        socketfile="ssh-%s.socket" % str(os.getpid())
        socket = os.path.expandvars('$XDG_RUNTIME_DIR/async/%s' % socketfile)
        # try:
        #    os.makedirs(os.path.dirname(socket))
        # except:
        #     pass

        self.ssh = SSHConnection(socket=None)

        self.ssh_args = ['-o ServerAliveInterval=60']
        if self.ssh_trust:
            self.ssh_args = self.ssh_args + ['-o LogLevel=quiet',
                                             '-o UserKnownHostsFile=/dev/null',
                                             '-o StrictHostKeyChecking=no']

        if self.ssh_key:
            self.ssh_args = self.ssh_args + ['-i', self.ssh_key]




    # Utilities
    # ----------------------------------------------------------------

    def wake_on_lan(self):
        if self.mac_address:
            cmd.wake_on_lan(self.mac_address)


    def power_off(self):
        self.run_cmd("sudo systemctl poweroff")


    def ping_delay(self, host):
        """Ping host and return the average time. None for offline"""

        pmin, pavg, pmax, pstdev = cmd.ping(host, timeout=2, num=2)
        return pavg


    def ssh_connect(self, alt_hostname=None):
        # TODO: if trusthost=False, check host keys

        try:
            if not self.ssh.alive():
                self.ssh.connect(hostname=self.ssh_hostname, user=self.user, alt_hostname=alt_hostname,
                                 timeout=30, args=self.ssh_args)

        except SSHConnectionError as err:
            raise SshError("Can't connect to %s: %s" % (self.ssh_hostname,
                                                        str(err)))


    def ssh_disconnect(self):
        if self.ssh.alive():
            self.ssh.close()


    def check_ssh(self):
        try:
            self.connect()
            return self.ssh.alive()

        except:
            pass

        return False



    # State transitions
    # ----------------------------------------------------------------

    def enter_state(self, state):
        if state == 'offline':
            pass

        elif state == 'running':
            self.wake_on_lan()

        elif state == 'online':
            self.connect()

        elif state == 'mounted':
            self.mount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    def leave_state(self, state):
        if state == 'offline':
            pass

        elif state == 'running':
            self.power_off()

        elif state == 'online':
            pass

        elif state == 'mounted':
            self.umount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    # Interface
    # ----------------------------------------------------------------

    def ping(self):
        """Pings the host and prints the delay"""
        ip = self.ip
        if ip:
            delay = self.ping_delay(ip)
            ui.print_color("%s (%s): %4.3f s" % (self.name, ip, delay))
        else:
            ui.print_color("%s: offline" % self.name)



    # Implementation
    # ----------------------------------------------------------------

    def _cache_hostname_and_ip(self):
        hostname, ip = self.ssh.resolve(hostname=self.ssh_hostname)
        self._ip = ip
        if hostname: self._hostname = hostname
        else:        self._hostname = ip


    @property
    def hostname(self):
        if self._hostname == None:
            self._cache_hostname_and_ip()

        return self._hostname


    @property
    def ip(self):
        if self._ip == None:
            self._cache_hostname_and_ip()

        return self._ip


    def connect(self):
        """Establish a connection to the server"""
        self.ssh_connect()


    def disconnect(self):
        """Close connection to the server"""
        self.ssh_disconnect()


    def get_state(self):
        """Queries the state of the host"""
        ui.print_debug("begin SshHost.get_state")
        self.state = 'offline'
        if self.check_ssh():                                 self.state = 'online'
        if self.state == 'online' and self.check_devices():  self.state = 'mounted'
        return self.state


    def get_info(self):
        """Gets a dictionary with host state parameters"""
        ui.print_debug("begin SshHost.get_info")
        info = {}

        info['state'] = self.get_state()
        if info['state'] in set(['mounted', 'online']):
            info['host'] = self.hostname
            info['ip'] = self.ip

        if info['state'] in set(['mounted']):
            size, available = self.df(self.path)
            info['size'] = size
            info['free'] = available

        return info


    def run_cmd(self, cm, tgtpath=None, catchout=False, stdin=None, silent=False):
        """Run a shell command in a given path at host"""
        path = tgtpath or self.path
        ui.print_debug("run_cmd. cmd: %s. path: %s" % (cm, path))

        try:
            ret = self.ssh.run('cd "%s" && %s' % (path, cm),
                               args = self.ssh_args,
                               catchout=catchout, stdin=stdin, silent=silent)
            return ret

        except SSHCmdError as err:
            raise CmdError(str(err), err.cmd, err.returncode, err.output)


    def interactive_shell(self):
        """Opens an interactive shell to host"""
        try:
            cmd.ssh(host=self.ssh_hostname, args=self.ssh_args)
            return 0
        except subprocess.CalledProcessError as err:
            return err.returncode


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
