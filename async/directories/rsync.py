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

import os
import subprocess

from async.directories.base import DirError, SyncError, InitError, HookError, CheckError
from async.directories.local import LocalDir
from async.hosts import SshHost, DirectoryHost

import async.cmd as cmd
import async.archui as ui

import subprocess

class RsyncDir(LocalDir):
    """Directory synced via rsync"""
    def __init__(self, conf):
        super(RsyncDir, self).__init__(conf)
        self.rsync_args = conf['rsync_args']



    # Interface
    # ----------------------------------------------------------------

    def type(self):
        """Returns the type of the directory as a string"""
        return 'rsync'


    def is_syncable(self):
        return True



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):
        src = '%s/' % self.fullpath(local)
        args = [] + self.rsync_args

        # do basic checks
        self.check_paths(local)
        self.check_paths(remote)

        # handle ignores
        ignore = set(self.ignore) | set(opts.ignore) | set(local.ignore) | set(remote.ignore)
        for p in ignore:
            args = args + ['--exclude=%s' % p]

        # get target path
        if isinstance(remote, SshHost):
            tgt = '%s@%s:%s/' % (remote.user, remote.hostname, self.fullpath(remote))

        elif isinstance(remote, DirectoryHost):
            tgt = '%s/' % self.fullpath(remote)

        else:
            raise DirError("Unsuported type %s for remote directory %s" % (remote.type, self.relpath))

        # chose sync direction
        if opts.force == 'down':
            src, tgt = tgt, src

        elif opts.force == 'up':
            pass

        else:
            raise SyncError("rsync directories need a direction. Use the --force")

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'pre_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)

        # sync
        ui.print_debug('rsync %s %s %s' % (' '.join(args), src, tgt))
        try:
            if not dryrun:
                cmd.rsync(src, tgt, args=args, silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'post_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
