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

from async.directories.base import BaseDir

import os
import async.archui as ui

class LocalDir(BaseDir):
    """Local directory that will not be synced."""
    def __init__(self, conf):
        super(LocalDir, self).__init__(conf)


    # Interface
    # ----------------------------------------------------------------
    def status(self, host):
        status = super(LocalDir, self).status(host)
        status['type'] = 'local'

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        return



    def init(self, host, silent=False, dryrun=False, opts=None):
        super(LocalDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts)
        path = self.fullpath(host)

        # run hooks
        self.run_hook(host, 'init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None):
        super(LocalDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
