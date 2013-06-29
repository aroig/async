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

from async.directories.base import BaseDir, DirError, SyncError, SetupError, HookError
from async.hosts import SshHost, DirectoryHost

import async.cmd as cmd
import async.archui as ui

import subprocess

class RsyncDir(BaseDir):
    """Directory synced via rsync"""
    def __init__(self, conf):
        super(RsyncDir, self).__init__(conf)
        self.ignore = conf['ignore']
        self.rsync_args = conf['rsync_args']


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        src = '%s/' % self.fullpath(local.path)
        args = [] + self.rsync_args

        for p in self.ignore:
            args = args + ['--exclude=%s' % p]

        if isinstance(remote, SshHost):
            tgt = '%s:%s/' % (remote.hostname, self.fullpath(remote.path))

        elif isinstance(remote, DirectoryHost):
            tgt = '%s/' % self.fullpath(remote.path)

        else:
            raise DirError("Unsuported type %s for remote directory %s" % (remote.type, self.relpath))

        # pre-sync hook
        ui.print_debug('pre_sync hook')
        try:
            if not dryrun: self.run_hook('pre_sync')
        except subprocess.CalledProcessError as err:
            raise HookError(str(err))

        # sync
        ui.print_debug('rsync %s %s %s' % (' '.join(args), src, tgt))
        try:
            if not dryrun: cmd.rsync(src, tgt, args=args, silent=silent)
        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        # post-sync hook
        ui.print_debug('post_sync hook')
        try:
            if not dryrun: self.run_hook('post_sync')
        except subprocess.CalledProcessError as err:
            raise HookError(str(err))



    def setup(self, host, silent=False, dryrun=False, opts=None):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
