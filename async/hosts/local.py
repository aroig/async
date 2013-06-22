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


from async.hosts.directory import DirectoryHost
from async.directories import SyncError, SetupError

import async.archui as ui


class LocalHost(DirectoryHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):
        super(LocalHost, self).__init__(conf)



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, silent=False, dryrun=False, opts=None):
        """Syncs local machine to this host"""
        failed = []
        if opts.dirs: dirs = opts.dirs
        else:         dirs = list(self.dirs.keys())

        keys = sorted(set(self.dirs.keys()) & set(dirs) & set(remote.dirs.keys()))
        num = len(keys)

        for i, k in enumerate(sorted(keys)):
            d = remote.dirs[k]
            if not silent: ui.print_enum(i+1, num, "syncing #*y%s#t (%s)" % (d.name, d.type))

            try:
                self.dirs[k].sync(self, remote, silent=silent, dryrun=dryrun, opts=opts)

            except SyncError as err:
                ui.print_error("synchronization failed")
                failed.append(d.name)

            print("")

        if len(failed) > 0:
            ui.print_error("synchronization failed on: %s" % ', '.join(failed))
            return 1
        else:
            return 0


    def setup(self, silent=False, dryrun=False, dirs=None, opts=None):
        """Prepares a host for the initial sync. sets up directories, and git annex repos"""
        failed = []
        if dirs == None: dirs = list(self.dirs.keys())

        keys = [k for k in self.dirs.keys() if k in set(dirs) and k in remote.dirs.keys()]
        num = len(keys)

        for i, k in enumerate(sorted(self.dirs.keys())):
            d = remote.dirs[k]
            if not silent: ui.print_enum(i+1, num, "setup #*y%s#t (%s)" % (d.name, d.type))

            try:
                self.dirs[k].setup(self, silent=silent, dryrun=dryrun, opts=opts)

            except SetupError as err:
                ui.print_error("setup failed")
                failed.append(d.name)

        if len(failed) > 0:
            ui.print_error("setup failed on: %s" % ', '.join(failed))
            return 1
        else:
            return 0



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
