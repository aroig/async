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

import async.cmd as cmd
import async.archui as ui

class AnnexDir(BaseDir):
    """Directory synced via git annex"""
    def __init__(self, basepath, conf):
        super(AnnexDir, self).__init__(basepath, conf)
        self.annex_get = conf['annex_get']

    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        src = local.dirs[self.name].path
        tgt = remote.dirs[self.name].path

        try:
            annex_args = ['sync', remote.name]
            ui.print_debug('git annex %s' % ' '.join(annex_args))
            if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=False)

            if self.annex_get:
                annex_args = ['get', '--from="%s"' % remote.name]
                ui.print_color('git annex %s' % ' '.join(annex_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=False)

            # TODO: run git annex get on the remote. Can't use cmd!!!

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))



    def setup(self, host, silent=False, dryrun=False, opts=None):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
