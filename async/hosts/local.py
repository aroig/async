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


from async.hosts.base import HostError
from async.hosts.directory import DirectoryHost
from async.directories import SyncError, InitError, CheckError, LocalDir, HookError

import async.archui as ui
from datetime import datetime


class LocalHost(DirectoryHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):
        super(LocalHost, self).__init__(conf)



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, silent=False, dryrun=False, opts=None):
        """Syncs local machine to this host"""
        dirs = self._get_common_dirs(self, remote, dirs=opts.dirs)

        # ignore LocalDir directores. Don't want to sync them
        dirs = {k: d for k, d in dirs.items() if not isinstance(d, LocalDir)}

        try:
            self.connect(silent=silent, dryrun=False)
            remote.connect(silent=silent, dryrun=False)

            def func(d):
                d.sync(self, remote, silent=silent or opts.terse, dryrun=dryrun,
                       opts=opts)

            return self.run_on_dirs(dirs, func, "Sync", silent=silent)

        except HostError as err:
            ui.print_error("can't connect to host: %s" % str(err))
            return False

        finally:
            remote.disconnect(silent=silent, dryrun=False)
            self.disconnect(silent=silent, dryrun=False)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
