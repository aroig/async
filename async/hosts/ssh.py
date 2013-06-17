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

import os
import sys
import paramiko

import async.archui as ui
import async.cmd as cmd

from async.hosts.base import BaseHost


class SshError(Exception):
    def __init__(self, msg=None):
        super(self, SshError).__init__(msg)


class AlwaysAcceptPolicy(paramiko.MissingHostKeyPolicy):
    """Policy for accepting connections without adding to known hosts."""
    def missing_host_key(self, client, hostname, key):
        return


class SshHost(BaseHost):
    """A remote ssh host"""
    def __init__(self, conf):

        # base config
        super(SshHost, self).__init__(conf)

        self.type = 'ssh'

        self.check = conf['check']

        # ssh related config
        self.hostname         = conf['hostname']         # the hostname
        self.user             = conf['user']             # the user on the remote
        self.ssh_key          = conf['ssh_key']          # the key for ssh connection
        self.ssh_trust        = conf['ssh_trust']

        self.ssh = paramiko.SSHClient()
        self.ssh_args = []
        if self.ssh_trust:
            self.ssh.set_missing_host_key_policy(AlwaysAcceptPolicy())

            self.ssh_args = self.ssh_args + ['-o LogLevel=quiet',
                                             '-o UserKnownHostsFile=/dev/null',
                                             '-o StrictHostKeyChecking=no']

        else:
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if self.ssh_key:
            self.ssh_args = self.ssh_args + ['-i %s' % remote.ssh_key]


    # Utilities
    # ----------------------------------------------------------------


    # Ssh
    # ----------------------------------------------------------------

    def ssh_status(self):
        """Returns the status of the ssh connection."""
        if self.ssh.get_transport() and self.ssh.get_transport().is_authenticated(): return 'open'
        else:                                                                        return 'closed'


    def ssh_connect(self):
        # TODO: if trusthost=False, check host keys
        self.ssh.connect(hostname=self.hostname, username=self.user, timeout=10,
                         key_filename=self.ssh_key, look_for_keys=False)

        if not self.wait_for('open', self.ssh_status):
            raise SshError("Can't connect to host: %s" % self.hostname)


    def ssh_disconnect(self):
        self.ssh.close()

        if not self.wait_for('closed', self.ssh_status):
            raise SshError("Can't disconnect from host: %s" % self.hostname)


    def ssh_cmd(self, tgtdir, cmd, catchout=False):
        """Executes a command on skynet via ssh and returns the output."""

        if self.ssh_status() == 'closed': self.connect_ssh()

        # TODO: what about stderr?
        if self.ssh_status() == 'open':
            stdin, stdout, stderr = self.ssh.exec_command('cd "%s" && %s' % (tgtdir, cmd))

            if catchout: return stdout.read()
            else:
                for line in stdout: sys.stdout.write(line)


    # Implementation
    # ----------------------------------------------------------------

    def host(self):
        """Returns the hostname."""
        return self.hostname

    def ip(self):
        """Returns the ip"""
        # TODO: sure?
        addr, port = self.ssh.get_transport().getpeername()
        return addr


    def get_state(self):
        """Queries the state of the host"""
        try:
            self.ssh_connect()
        except SshError:
            return 'offline'

        # TODO: Check whether stuff is mounted
        return 'online'


    def set_state(self, state):
        """Sets the state of the host"""
        # TODO
        pass


    def get_info(self):
        """Gets a dictionary with host state parameters"""
        info = {}

        info['state'] = self.get_state()
        if info['state'] in set(['mounted', 'online']):
            info['host'] = self.host()
            info['ip'] = self.ip()

        if info['state'] in set(['mounted']):
            size, available = self.df(self.path)
            info['size'] = size
            info['free'] = available

        return info


    def run_cmd(self, c, tgtpath=None, catchout=False):
        """Run a shell command in a given path at host"""
        path = tgtpath or self.path
        return self.ssh_cmd(tgtdir=path, cmd=c, catchout=catchout)


    def run_script(self, scr_path):
        """Run script on a local path on the host"""
        raise NotImplementedError


    def interactive_shell(self):
        """Opens an interactive shell to host"""
        cmd.ssh(host=self.hostname)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
