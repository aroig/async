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

from async.directories.base import BaseDir

import os
import async.archui as ui

class LocalDir(BaseDir):
    """Local directory that will not be synced."""
    def __init__(self, conf):
        super(LocalDir, self).__init__(conf)
        self.lastsync = False


    # Interface
    # ----------------------------------------------------------------

    def is_syncable(self):
        return False


    def status(self, host, slow=False):
        status = super(LocalDir, self).status(host, slow=slow)
        path = os.path.join(host.path, self.relpath)
        status['type'] = 'local'

        # number of files
        if slow:
            try:
                raw = host.run_cmd("find . -not -type d -and  -print | wc -l",
                                   tgtpath=path, catchout=True).strip()
                status['numfiles'] = int(raw)
            except:
                status['numfiles'] = -1

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):

        # do basic checks
        self.check_paths(local)
        self.check_paths(remote)

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'pre_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)

        # call sync on the parent
        super(GitDir, self).sync(local, remote, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'post_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_init', tgt=path, silent=silent, dryrun=dryrun)

        super(LocalDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # do basic checks
        self.check_paths(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'check', tgt=path, silent=silent, dryrun=dryrun)

        super(LocalDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
