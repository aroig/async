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


from async.hosts.base import BaseHost


class SyncError(Exception):
    def __init__(self, msg=None):
        super(self, SyncError).__init__(msg)


class LocalHost(BaseHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):

        # base config
        super(SshHost, self).__init__(conf)

        self.type = 'local'



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, opts):
        """Syncs local machine to this host"""
        failed = []

        num = len(dirs)
        for i, k in enumerate(self.dirs.keys()):
            ui.print_enum(i, num, "syncing #y%s#t" % d['name'])
            if k in remote.dirs.keys():
                try:
                    self.dirs[k].sync(self, remote, opts)

                except SyncError as err:
                    ui.print_error("synchronization failed. %s" % str(err))
                    failed.append(d['name'])

        if len(failed) > 0:
            ui.print_error("synchronization failed on: %s" % ', '.join(failed))
            return 1
        else:
            return 0


    def setup(self, opts):
        """Prepares a host for the initial sync. sets up directories, and git annex repos"""
        # TODO
        pass



    # Abstract methods
    # ----------------------------------------------------------------




# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
