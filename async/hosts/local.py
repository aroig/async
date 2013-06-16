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


class SyncError(Exception):
    def __init__(self, msg=None):
        super(self, SyncError).__init__(msg)


class SetupError(Exception):
    def __init__(self, msg=None):
        super(self, SetupError).__init__(msg)


class LocalHost(DirectoryHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):

        # base config
        super(LocalHost, self).__init__(conf)

        self.type = 'local'



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, silent=False, dryrun=False, dirs=None, opts=None):
        """Syncs local machine to this host"""
        failed = []

        num = len(dirs)
        for i, k in enumerate(sorted(self.dirs.keys())):
            if not k in remote.dirs.keys() or (dirs and not k in dirs):
                continue

            d = remote.dirs[k]
            if not silent: ui.print_enum(i, num, "syncing #y%s#t (%s)" % (d.name, d.type))

            try:
                if not dryrun: self.dirs[k].sync(self, remote, opts=opts)

            except SyncError as err:
                ui.print_error("synchronization failed. %s" % str(err))
                failed.append(d['name'])

        if len(failed) > 0:
            ui.print_error("synchronization failed on: %s" % ', '.join(failed))
            return 1
        else:
            return 0


    def setup(self, silent=False, dryrun=False, dirs=None, opts=None):
        """Prepares a host for the initial sync. sets up directories, and git annex repos"""
        failed = []

        num = len(dirs)
        for i, k in enumerate(sorted(self.dirs.keys())):
            if dirs and not k in dirs:
                continue

            d = remote.dirs[k]
            if not silent: ui.print_enum(i, num, "setup #y%s#t (%s)" % (d.name, d.type))

            try:
                if not dryrun: self.dirs[k].setup(self, opts=opts)

            except SetupError as err:
                ui.print_error("setup failed. %s" % str(err))
                failed.append(d['name'])

        if len(failed) > 0:
            ui.print_error("setup failed on: %s" % ', '.join(failed))
            return 1
        else:
            return 0



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
