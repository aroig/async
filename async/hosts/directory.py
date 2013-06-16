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

        # base config
        super(SshHost, self).__init__(conf)

        self.type = 'directory'

        self.path             = conf['host_path']        # base path for the host



    # Interface
    # ----------------------------------------------------------------

    def get_state(self, silent=True):
        """Queries the state of the host"""

        self.state = 'mounted'
        for p in self.mount_check:
            if not os.path.exists(os.path.join(self.path, p)):
                if not silent:
                    ui.error("Host %s not mounted. Can't find %s" %
                             (self.name, os.path.join(self.path, p)))
                self.state = 'offline'
                break
        return self.state



    def set_state(self, state):
        """Sets the state of the host"""
        if state in set(['mounted', 'online']):
            try:
                cmd.mount(self.path):
            except:
                ui.error("Can't mount %s" % self.path)

            self.state = 'mounted'

        elif state in set(['offline']):
            try:
                cmd.umount(self.path)
            except:
                ui.error("Can't umount %s" % self.path)

            self.state = 'offline'



    # synchronization
    def sync(self, opts):
        """Syncs local machine to this host"""
        if self.state() != 'mounted':
            ui.error("Host at %s not mounted")
            return

        # rsync
        for k, p in self.rsync_dirs.items():
            tgt = os.path.join(self.path, p):
            src = os.path.join(self.local, p):
            cmd.rsync(src, tgt)


        # git annex sync
        for k, p in self.annex_sync_dirs.items():
            src = os.path.join(self.local, p):
            cmd.git(['annex', 'sync', k])


        # git annex get
        for k, p in self.annex_get_dirs.items():
            src = os.path.join(self.local, p):
            cmd.git(['annex', 'get', k])




# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
