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

        # ssh related config
        self.hostname         = conf['hostname']         # the hostname
        self.user             = conf['user']             # the user on the remote
        self.ssh_key          = conf['ssh_key']          # the key for ssh connection
        self.trust            = conf['trust']

        # ssh
        self.ssh = paramiko.SSHClient()
        if self.trust:
            self.ssh.set_missing_host_key_policy(AlwaysAcceptPolicy())


    # Ssh
    # ----------------------------------------------------------------

    def ssh_status(self):
        """Returns the status of the ssh connection."""
        if self.ssh.get_transport() and self.ssh.get_transport().is_authenticated(): return 'open'
        else:                                                                        return 'closed'


    def ssh_connect(self):
        # TODO: if trusthost=False, check host keys
        self.ssh.connect(hostname=self.hostname, username=self.user,
                         key_filename=self.ssh_key, look_for_keys=False)

        if not self.wait_for('open', self.ssh_status):
            raise SshError("Can't connect to host: %s" % self.hostname)


    def ssh_disconnect(self):
        self.ssh.close()

        if not self.wait_for('closed', self.ssh_status):
            raise SshError("Can't disconnect from host: %s" % self.hostname)


    def ssh_cmd(self, cmd):
        """Executes a command on skynet via ssh and returns the output."""

        if self.ssh_status() == 'closed': self.connect_ssh()

        if self.ssh_status() == 'open':
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
            return stdout.read()




    # Interface
    # ----------------------------------------------------------------

    def get_state(self, silent=True):
        """Queries the state of the host"""
        # TODO
        pass



    def set_state(self, state):
        """Sets the state of the host"""
        # TODO
        pass


    # synchronization
    def sync(self, opts):
        """Syncs local machine to this host"""
        if self.state() != 'mounted':
            ui.error("Host at %s not mounted")
            return

        # rsync
        for k, p in self.rsync_dirs.items():
            tgt = os.path.join(self.path, p)
            src = os.path.join(self.local, p)
            cmd.rsync(src, tgt)


        # git annex sync
        for k, p in self.annex_sync_dirs.items():
            src = os.path.join(self.local, p)
            cmd.git(['annex', 'sync', k])


        # git annex get
        for k, p in self.annex_get_dirs.items():
            src = os.path.join(self.local, p)
            cmd.git(['annex', 'get', k])




# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
