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

from async.directories.base import BaseDir, DirError

import async.hosts as hosts
import async.cmd as cmd
import async.archui as ui

class RsyncDir(BaseDir):
    """Directory synced via rsync"""
    def __init__(self, basepath, conf):
        super(RsyncDir, self).__init__(basepath, conf)


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, opts=None, dryrun=False):
        src = '%s/' % local.dirs[self.name].path
        args = ['-avq', '--delete']

        if isinstance(remote, hosts.SshHost):
            tgt = '%s:%s/' % (remote.hostname, remote.dirs[self.name].path)

        elif isinstance(remote, hosts.DirectoryHost):
            tgt = '%s/' % remote.dirs[self.name].path

        else:
            raise DirError("Unsuported type %s for remote directory %s" % (remote.type, self.relpath))

        ui.print_debug('rsync %s %s %s' % (' '.join(args), src, tgt))
        if not dryrun: cmd.rsync(src, tgt, args=args, silent=False)


    def setup(self, host, opts=None, dryrun=False):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
