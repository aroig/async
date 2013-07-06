#!/usr/bin/env python2
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

import async.archui as ui
import async.cmd as cmd

from async.hosts.base import BaseHost, HostError
from async.openssh import SSHConnection, SSHConnectionError

class SshError(HostError):
    def __init__(self, msg=None):
        super(SshError, self).__init__(msg)


class SshHost(BaseHost):
    """A remote ssh host"""

    STATES = ['offline', 'online', 'mounted']

    def __init__(self, conf):
        ui.print_debug("begin SshHost.__init__")
        super(SshHost, self).__init__(conf)

        self.check = conf['check']

        # ssh related config
        self._hostname         = conf['hostname']         # the hostname
        self.user             = conf['user']             # the user on the remote
        self.ssh_key          = conf['ssh_key']          # the key for ssh connection
        self.ssh_trust        = conf['ssh_trust']

        socket = os.path.expandvars('$XDG_RUNTIME_DIR/async/ssh.socket')
        try:
            os.makedirs(os.path.dirname(socket))
        except:
            pass
        self.ssh = SSHConnection(socket=socket)

        self.ssh_args = []
        if self.ssh_trust:
            self.ssh_args = self.ssh_args + ['-o LogLevel=quiet',
                                             '-o UserKnownHostsFile=/dev/null',
                                             '-o StrictHostKeyChecking=no']

        if self.ssh_key:
            self.ssh_args = self.ssh_args + ['-i', self.ssh_key]


    def __del__(self):
        self.ssh.close()


    # Utilities
    # ----------------------------------------------------------------

    def wake_on_lan(self):
        # TODO
        pass

    def power_off(self):
        # TODO
        pass


    def ping_delay(self):
        """Ping host and return the average time. None for offline"""

        pmin, pavg, pmax, pstdev = cmd.ping(self.ip, timeout=2, num=2)
        return pavg


    # Ssh
    # ----------------------------------------------------------------

    def check_ssh(self):
        """Returns true if ssh connection is live and authenticated"""
        return self.ssh.alive()


    def ssh_connect(self):
        # TODO: if trusthost=False, check host keys

        try:
            if not self.ssh.connected():
                self.ssh.connect(hostname=self.hostname, user=self.user,
                                 timeout=10, args=self.ssh_args)

        except SSHConnectionError as err:
            raise SshError("Can't connect to %s: %s" % (self.hostname, str(err)))

        # if not self.wait_for(True, self.check_ssh):
        #     raise SshError("Can't connect to %s" % self.hostname)


    def ssh_disconnect(self):
        if ssh.connected():
            self.ssh.close()

        if not self.wait_for(False, self.check_ssh):
            raise SshError("Can't disconnect from host: %s" % self.hostname)


    # State transitions
    # ----------------------------------------------------------------

    def enter_state(self, state):
        if state == 'offline':
            pass

        elif state == 'online':
            self.wake_on_lan()

        elif state == 'mounted':
            self.mount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    def leave_state(self, state):
        if state == 'offline':
            pass

        elif state == 'online':
            self.power_off()

        elif state == 'mounted':
            self.umount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    # Interface
    # ----------------------------------------------------------------

    def ping(self):
        """Pings the host and prints the delay"""
        ui.print_color("%s (%s): %4.3f s" % (self.name, self.ip, self.ping_delay()))



    # Implementation
    # ----------------------------------------------------------------

    @property
    def hostname(self):
        return self._hostname


    @property
    def ip(self):
        """Returns the ip"""
        # TODO: get the IP somehow
        return None


    def connect(self, silent=False, dryrun=False):
        """Establishes a connection and initialized data"""

        def func():
            self.ssh_connect()

        self.run_with_message(func=func,
                              msg="Connecting to %s" % self.name,
                              silent=silent,
                              dryrun=dryrun)
        self.get_state()


    def disconnect(self, silent=False, dryrun=False):
        def func():
            self.ssh.close()

        self.run_with_message(func=func,
                              msg="Disconnecting from %s" % self.name,
                              silent=silent,
                              dryrun=dryrun)


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


    def run_cmd(self, c, tgtpath=None, catchout=False):
        """Run a shell command in a given path at host"""
        path = tgtpath or self.path

        return self.ssh.run('cd "%s" && %s' % (path, c),
                            args = self.ssh_args, catchout=catchout)


    def run_script(self, scr_path):
        """Run script on a local path on the host"""
        raise NotImplementedError


    def interactive_shell(self):
        """Opens an interactive shell to host"""
        cmd.ssh(host=self.hostname, args=self.ssh_args)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
