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

import subprocess

from async.directories.base import BaseDir, DirError, SyncError, SetupError
from async.hosts import SshHost, DirectoryHost

import async.cmd as cmd
import async.archui as ui

class UnisonDir(BaseDir):
    """Directory synced via unison"""
    def __init__(self, basepath, conf):
        super(UnisonDir, self).__init__(basepath, conf)


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        src = '%s/' % local.path

        if isinstance(remote, SshHost):
            tgt = 'ssh://%s@%s/%s/' % (remote.user, remote.hostname, remote.path)
            tgtalias = 'ssh://%s/%s/' % (remote.name, remote.path)

        elif isinstance(remote, DirectoryHost):
            tgt = remote.path
            tgtalias = remote.path

        else:
            raise DirError("Unsuported type %s for remote directory %s" % (remote.type, self.relpath))

        sshargs = []
        sshargs = sshargs + remote.ssh_args

        args = ['-root', src,
                '-root', tgt,
                '-rootalias', '%s -> %s' % (tgt, tgtalias),
                '-path', self.relpath,
                '-follow', 'Path %s' % self.relpath]

        if opts.auto:  args = args + ['-auto']
        if opts.slow:  args = args + ['-fastcheck' 'false']
        if opts.batch: args = args + ['-batch']

        if opts.force == 'up':   args = args + ['-force', src]
        if opts.force == 'down': args = args + ['-force', tgt]

        if len(sshargs) > 0:     args = args + ['-sshargs', ' '.join(sshargs)]

        ui.print_color('unison %s' % ' '.join(args))
        try:
            if not dryrun: cmd.unison(args=args, silent=silent)
        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))



    def setup(self, host, silent=False, dryrun=False, opts=None):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
