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

from async.directories.base import BaseDir, DirError, SyncError, SetupError
import subprocess

import async.cmd as cmd
import async.archui as ui

class AnnexDir(BaseDir):
    """Directory synced via git annex"""
    def __init__(self, conf):
        super(AnnexDir, self).__init__(conf)
        self.annex_copy_data = conf['annex_copy_data']

    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        annex_sync_args = ['sync', remote.name]
        annex_get_args  = ['copy', '--fast', '--from="%s"' % remote.name]
        annex_send_args = ['copy', '--fast', '--to="%s"' % remote.name]

        # pre-sync hook
        ui.print_debug('pre_sync hook')
        try:
            if not dryrun: self.run_hook('pre_sync')
        except subprocess.CalledProcessError as err:
            raise HookError(str(err))

        # sync
        ui.print_debug('git annex %s' % ' '.join(annex_sync_args))
        try:
            if not dryrun: cmd.annex(tgtdir=src, args=annex_sync_args, silent=False)
        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        if self.annex_copy_data:
            try:
                ui.print_debug('git annex %s' % ' '.join(annex_get_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_get_args, silent=False)

                ui.print_debug('git annex %s' % ' '.join(annex_send_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_get_args, silent=False)

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
