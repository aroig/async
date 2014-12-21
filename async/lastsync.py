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

from datetime import datetime, timedelta

from async.hosts.base import HostError
from async.hosts.directory import DirectoryHost
from async.directories import SyncError, InitError, CheckError, LocalDir, HookError, SkipError

import async.archui as ui


class LastSync:
    def __init__(self, local, remote, directory, checkopts):
        self.local = local
        self.remote = remote
        self.directory = directory
        self.checkopts = checkopts
        self.success = False

        # check paths
        if self.directory != None:
            self.directory.check_paths(self.local)
            self.directory.check_paths(self.remote)


    def checkdir_lastsync(self, local, remote, d, opts):
        """Check whether last sync failed on a different host"""

        from async.directories.base import SyncError, SkipError

        lls = local.read_lastsync(d.fullpath(local))
        rls = remote.read_lastsync(d.fullpath(remote))

        # fail if an ongoing sync
        if lls['busy']:
            raise SyncError("There is an ongoing sync on %s" % local.name)

        if rls['busy']:
            raise SyncError("There is an ongoing sync on %s" % remote.name)

        # only sync if last sync failed
        if opts.failed:
            if lls['success']:
                raise SkipError("last sync succeeded")

        # only sync if older than opts.older
        if opts.older > 0:
            threshold = datetime.today() - timedelta(minutes=opts.older)
            if lls['timestamp'] and lls['timestamp'] > threshold:
                raise SkipError("last sync less than %d minutes ago" % opts.older)

        # only sync if last sync failed or done from a different host
        if opts.needed:
            if lls['success'] and rls['success'] and lls['remote'] == remote.name and rls['remote'] == local.name:
                raise SkipError("successful last sync from the same host")

        # fail if last sync failed from a different host
        if not opts.force:
            if not lls['success'] and lls['remote'] != remote.name:
                raise SyncError("failed last sync on '%s' from a different host. Use the --force" % local.name)

            if not rls['success'] and rls['remote'] != local.name:
                raise SyncError("failed last sync on '%s' from a different host. Use the --force" % remote.name)

        return True


    def __enter__(self):
        # perform check to lastsync data
        if self.directory != None and self.directory.lastsync:
            self.checkdir_lastsync(self.local, self.remote, self.directory, self.checkopts)

        # signal begining of sync
        for h, r in [(self.local, self.remote), (self.remote, self.local)]:
            if self.directory != None:
                dirpath = self.directory.fullpath(h)
                do_lastsync = h.lastsync and self.directory.lastsync
            else:
                dirpath = h.path
                do_lastsync = h.lastsync

            if do_lastsync: h.signal_lastsync(dirpath, r.name)
        return self

    def __exit__(self, type, value, traceback):
        if isinstance(value, SkipError):
            self.success = True

        for h, r in [(self.local, self.remote), (self.remote, self.local)]:
            if self.directory != None:
                dirpath = self.directory.fullpath(h)
                do_lastsync = h.lastsync and self.directory.lastsync

            else:
                dirpath = h.path
                do_lastsync = h.lastsync

            if do_lastsync: h.save_lastsync(dirpath, r.name, self.success)
