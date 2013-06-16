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

import async.cmd as cmd

class AnnexDir(BaseDir):

    def __init__(self, basepath, conf):
        super(AnnexDir, self).__init__(basepath, conf)


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, opts):
        src = local.dirs[self.name].path
        tgt = remote.dirs[self.name].path

        local.run_cmd('git annex sync "%s"' % remote.name, path=src)

        # TODO: if get, do a local and remote get
        # local.run_cmd('git annex get --from="%s"' % remote.name, path=src)
        # remote.run_cmd('git annex get --from="%s"' % local.name, path=tgt)


    def setup(self, host, opts):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
