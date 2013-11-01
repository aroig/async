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
from async.pathdict import PathDict

import async.archui as ui
from datetime import datetime


class LocalHost(DirectoryHost):
    """Represents the localhost. Does not sync, only useful for initial setup and status."""

    STATES = ['offline', 'online', 'mounted']
    def __init__(self, conf):
        super(LocalHost, self).__init__(conf)


    def _get_common_dirs(self, A, B, dirs):
        """returns a dict of dir objects that are common in A and B as paths. Only allows for
        directories with name in dirs, if dirs != None."""
        if dirs != None: dirs = set(dirs)

        pdA = PathDict({d.relpath: d for k, d in A.items()})
        pdB = PathDict({d.relpath: d for k, d in B.items()})
        pdI = pdA & pdB
        return {d.name: d for p, d in pdI.items() if dirs==None or d.name in dirs}



    # Interface
    # ----------------------------------------------------------------

    def sync(self, remote, silent=False, dryrun=False, opts=None):
        """Syncs local machine to this host"""
        failed = []

        dirs = self._get_common_dirs(self.dirs, remote.dirs, dirs=opts.dirs)
        dirs = {k: d for k, d in dirs.items() if not isinstance(d, LocalDir)}
        keys = sorted(dirs.keys())
        num = len(dirs)
        ret = True

        try:
            remote.connect(silent=silent, dryrun=False)

            # mount remote
            remote_state = remote.get_state()
            if not remote.set_state('mounted') == 'mounted':
                ui.print_error("Remote host is not in 'mounted' state")
                return False

            ui.print_status("Synchronizing with #*m%s#t. %s" % (remote.name,
                                                                datetime.now().strftime("%a %d %b %Y %H:%M")))
            ui.print_color("")

            for i, k in enumerate(keys):
                d = dirs[k]
                if not silent: ui.print_enum(i+1, num, "syncing #*y%s#t (%s)" % (d.name, d.type))

                try:
                    d.sync(self, remote, silent=silent or opts.terse,
                           dryrun=dryrun, opts=opts)

                except SyncError as err:
                    ui.print_error("synchronization failed: %s" % str(err))
                    failed.append(d.name)

                except HookError as err:
                    ui.print_error("hook failed: %s" % str(err))
                    failed.append(d.name)

                ui.print_color("")

            # recover old remote state
            remote.set_state(remote_state)

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        finally:
            remote.disconnect(silent=silent, dryrun=False)

        ui.print_color("")

        # success message
        if len(failed) == 0 and ret == True:
            ui.print_color("Synchronization with #*m%s#t #*gsuceeded#t." % remote.name)
            ui.print_color("")
            return True

        elif len(failed) > 0 or ret == False:
            ui.print_color("Synchronization with #*m%s#t #*rfailed#t." % remote.name)
            ui.print_color("  directories: %s" % ', '.join(failed))
            ui.print_color("")
            return False



    def check(self, silent=False, dryrun=False, opts=None):
        """Check directories for local machine"""
        failed = []

        dirs = self._get_common_dirs(self.dirs, self.dirs, dirs=opts.dirs)
        dirs = {k: d for k, d in dirs.items() if not isinstance(d, LocalDir)}
        keys = sorted(dirs.keys())
        num = len(dirs)
        ret = True

        try:
            ui.print_status("Checking localhost directories. %s" % datetime.now().strftime("%a %d %b %Y %H:%M"))
            ui.print_color("")

            for i, k in enumerate(keys):
                d = dirs[k]
                if not silent: ui.print_enum(i+1, num, "checking #*y%s#t (%s)" % (d.name, d.type))

                try:
                    d.check(self, silent=silent or opts.terse, dryrun=dryrun, opts=opts)

                except CheckError as err:
                    ui.print_error("check failed: %s" % str(err))
                    failed.append(d.name)

                ui.print_color("")

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        # success message
        if len(failed) == 0 and ret == True:
            ui.print_color("Check #*gsuceeded#t.")
            ui.print_color("")
            return True

        elif len(failed) > 0 or ret == False:
            ui.print_color("Check #*rfailed#t.")
            ui.print_color("  directories: %s" % ', '.join(failed))
            ui.print_color("")
            return False



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
