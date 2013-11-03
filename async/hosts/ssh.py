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

    STATES = ['offline', 'online', 'mounted']

    def __init__(self, conf):
        ui.print_debug("begin SshHost.__init__")
        super(SshHost, self).__init__(conf)

        # ssh related config
        self.ssh_hostname     = conf['hostname']         # the hostname
        self.user             = conf['user']             # the user on the remote
        self.mac_address      = conf['mac_address']      # mac address
        self.ssh_key          = conf['ssh_key']          # the key for ssh connection
        self.ssh_trust        = conf['ssh_trust']

        socketfile="ssh-%s.socket" % str(os.getpid())
        socket = os.path.expandvars('$XDG_RUNTIME_DIR/async/%s' % socketfile)
        try:
            os.makedirs(os.path.dirname(socket))
        except:
            pass
        self.ssh = SSHConnection(socket=socket)

        self.ssh_args = ['-o ServerAliveInterval=60']
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
        if self.mac_address:
            cmd.wake_on_lan(self.mac_address)


    def power_off(self):
        self.run_cmd("sudo systemctl poweroff")


    def ping_delay(self, host):
        """Ping host and return the average time. None for offline"""

        pmin, pavg, pmax, pstdev = cmd.ping(host, timeout=2, num=2)
        return pavg



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
        ip = self.ip
        if ip:
            delay = self.ping_delay(ip)
            ui.print_color("%s (%s): %4.3f s" % (self.name, ip, delay))
        else:
            ui.print_color("%s: offline" % self.name)



    # Implementation
    # ----------------------------------------------------------------

    @property
    def hostname(self):
        hostname, ip = self.ssh.resolve(hostname=self.ssh_hostname)
        return hostname


    @property
    def ip(self):
        hostname, ip = self.ssh.resolve(hostname=self.ssh_hostname)
        return ip


    def connect(self, silent=False, dryrun=False):
        """Establishes a connection and initialized data"""

        def func():
            # TODO: if trusthost=False, check host keys

            try:
                if not self.ssh.alive():
                    self.ssh.connect(hostname=self.ssh_hostname, user=self.user,
                                     timeout=30, args=self.ssh_args)

            except SSHConnectionError as err:
                raise SshError("Can't connect to %s: %s" % (self.ssh_hostname,
                                                            str(err)))

            # if not self.wait_for(True, self.ssh.alive):
            #     raise SshError("Can't connect to %s" % self.ssh_hostname)

        try:
            self.run_with_message(func=func,
                                  msg="Connecting to %s" % self.name,
                                  silent=silent,
                                  dryrun=dryrun)
        finally:
            self.get_state()


    def disconnect(self, silent=False, dryrun=False):
        def func():
            if self.ssh.alive():
                self.ssh.close()

            # if not self.wait_for(False, self.ssh.alive):
            #    raise SshError("Can't disconnect from host: %s" % self.ssh_hostname)

        self.run_with_message(func=func,
                              msg="Disconnecting from %s" % self.name,
                              silent=silent,
                              dryrun=dryrun)


    def get_state(self):
        """Queries the state of the host"""
        ui.print_debug("begin SshHost.get_state")
        self.state = 'offline'
        if self.ssh.alive():                                 self.state = 'online'
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


    def run_cmd(self, cm, tgtpath=None, catchout=False, stdin=None):
        """Run a shell command in a given path at host"""
        path = tgtpath or self.path

        try:
            ret = self.ssh.run('cd "%s" && %s' % (path, cm),
                               args = self.ssh_args,
                               catchout=catchout, stdin=stdin)
            return ret

        except SSHCmdError as err:
            raise CmdError(str(err), err.returncode, err.output)


    def interactive_shell(self):
        """Opens an interactive shell to host"""
        try:
            cmd.ssh(host=self.ssh_hostname, args=self.ssh_args)
            return 0
        except subprocess.CalledProcessError as err:
            return err.returncode


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
