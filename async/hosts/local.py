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


from collections import OrderedDict

from async.hosts.base import HostError
from async.hosts.directory import DirectoryHost
from async.directories import SyncError, InitError, CheckError, LocalDir, HookError, SkipError
from async.lastsync import LastSync

import async.archui as ui


class LocalHost(DirectoryHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):
        super(LocalHost, self).__init__(conf)



    def _baseobject(self, d1, d2):
        """Returns the object whose type is less specialized, or None if they are not
        specialization of one another

        """
        if isinstance(d1, type(d2)) and isinstance(d2, type(d1)):
            return d1

        elif isinstance(d2, type(d1)) and not isinstance(d1, type(d2)):
            return d1

        elif isinstance(d1, type(d2)) and not isinstance(d2, type(d1)):
            return d2

        else:
            return None



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, silent=False, dryrun=False, opts=None):
        """Syncs local machine to this host"""
        dirs = (self.dirs & remote.dirs).data(keys=opts.dirs, ignore=opts.ignore)

        # keep actual directories which are syncable, and indexed by name.
        filtdirs = OrderedDict()
        for k, d in dirs.items():
            dloc = self.directory(k)
            if dloc == None:
                ui.print_warning("Unknown directory '%s' on host '%s'" % (k, self.name))
                continue

            drem = remote.directory(k)
            if drem == None:
                ui.print_warning("Unknown directory '%s' on host '%s'" % (k, remote.name))
                continue

            dd = self._baseobject(dloc, drem)
            if dd == None:
                ui.print_warning("Incompatible directory types for '%s': %s, %s" % (k, dloc.type(), drem.type()))
                continue

            if dd.is_syncable():
                filtdirs[dd.name] = dd

        ret = False
        try:
            with remote.in_state('mounted', silent=silent, dryrun=dryrun):
                def func(d):
                    with LastSync(self, remote, d, opts) as ls:
                        # synchronze
                        d.sync(self, remote, silent=silent or opts.terse,
                               dryrun=dryrun, opts=opts)
                        ls.success=True

                with LastSync(self, remote, None, None) as rls:
                    ret = self.run_on_dirs(filtdirs, func, "Sync",
                                           desc="%s <-> %s" % (self.name, remote.name),
                                           silent=silent, dryrun=dryrun)
                    rls.success = ret

        except HostError as err:
            ui.print_error(str(err))
            return False

        return ret


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
