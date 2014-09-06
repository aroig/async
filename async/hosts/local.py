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


from collections import OrderedDict

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

    def __enter__(self):
        # perform check to lastsync data
        if self.directory != None:
            self.local.checkdir_lastsync(self.remote, self.directory, self.checkopts)

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



class LocalHost(DirectoryHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):
        super(LocalHost, self).__init__(conf)



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, silent=False, dryrun=False, opts=None):
        """Syncs local machine to this host"""
        dirs = self._get_common_dirs(self, remote, dirs=opts.dirs, ignore=opts.ignore)

        # ignore LocalDir directores. Don't want to sync them
        dirs = OrderedDict([(k, d) for k, d in dirs.items() if not isinstance(d, LocalDir)])

        ret = False
        try:
            with remote.in_state('mounted', silent=silent, dryrun=dryrun):
                def func(d):
                    try:
                        with LastSync(self, remote, d, opts) as ls:
                            # synchronze
                            d.sync(self, remote, silent=silent or opts.terse,
                                   dryrun=dryrun, opts=opts)
                            ls.success=True

                    except SkipError as err:
                        ui.print_color("skipping: %s" % str(err))

                with LastSync(self, remote, None, None) as rls:
                    ret = self.run_on_dirs(dirs, func, "Sync",
                                           desc="%s <-> %s" % (self.name, remote.name),
                                           silent=silent, dryrun=dryrun)
                    rls.success = ret

        except HostError as err:
            ui.print_error(str(err))
            return False

        return ret


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
