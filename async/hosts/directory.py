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

import async.archui as ui
import async.cmd as cmd

from async.hosts.base import BaseHost

class DirectoryHost(BaseHost):
    """Host representing a local directory. A USB mountpoint, for instance"""
    def __init__(self, conf):
        super(DirectoryHost, self).__init__(conf=conf)


    # State transitions
    # ----------------------------------------------------------------

    def enter_state(self, state):
        if state == 'offline':
            pass

        elif state == 'online':
            pass

        elif state == 'mounted':
            self.mount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    def leave_state(self, state):
        if state == 'offline':
            pass

        elif state == 'online':
            pass

        elif state == 'mounted':
            self.umount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    # Implementation
    # ----------------------------------------------------------------

    def connect(self):
        """Establishes a connection and initialized data"""
        try:
            self.get_state()
        except SshError:
            ui.print_error("Can't connect to host")


    def get_state(self):
        """Queries the state of the host"""

        if self.check_devices():  self.state = 'mounted'
        else:                     self.state = 'offline'

        return self.state


    def get_info(self):
        """Gets a dictionary with host state parameters"""
        info = {}

        info['state'] = self.get_state()
        if info['state'] in set(['mounted']):
            size, available = self.df(self.path)
            info['size'] = size
            info['free'] = available

        return info


    def run_cmd(self, c, tgtpath=None, catchout=False):
        """Run a shell command in a given path at host"""
        path = tgtpath or self.path
        return cmd.bash_cmd(tgtdir=path, cmd=c, catchout=catchout)


    def run_script(self, scrpath, path):
        """Run script on a local path on the host"""
        raise NotImplementedError


    def interactive_shell(self):
        """Opens an interactive shell to host"""
        cmd.shell(self.path)





# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
