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

from async.directories.base import BaseDir, DirError, SyncError, SetupError, HookError
from async.hosts import SshHost, DirectoryHost

import async.cmd as cmd
import async.archui as ui

class UnisonDir(BaseDir):
    """Directory synced via unison"""
    def __init__(self, conf):
        super(UnisonDir, self).__init__(conf)

        self.unison_args = conf['unison_args']
        self.unison_profile = conf['unison_profile']
        self.ignore = conf['ignore']


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
                '-follow', 'Path %s' % self.relpath,
                '-logfile', '/dev/null',
            ]

        args = args + self.unison_args

        for p in self.ignore:
            args = args + ['-ignore', 'Path %s' % p]

        for p in opts.ignore:
            args = args + ['-ignore', 'Path %s' % p]

        if opts.auto:  args = args + ['-auto']
        if opts.slow:  args = args + ['-fastcheck' 'false']
        if opts.batch: args = args + ['-batch']

        if opts.force == 'up':   args = args + ['-force', src]
        if opts.force == 'down': args = args + ['-force', tgt]

        if len(sshargs) > 0:     args = args + ['-sshargs', ' '.join(sshargs)]

        args = args + [self.unison_profile]

        # pre-sync hook
        ui.print_debug('pre_sync hook')
        if not dryrun: self.run_hook(local, 'pre_sync')

        # sync
        ui.print_debug('unison %s' % ' '.join(args))
        try:
            if not dryrun: cmd.unison(args=args, silent=silent)
        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        # post-sync hook
        ui.print_debug('post_sync hook')
        if not dryrun: self.run_hook(local, 'post_sync')


    def setup(self, host, silent=False, dryrun=False, opts=None):
        ui.print_debug('create directory')
        path = self.fullpath()
        new = self._create_directory(host, path, self.perms, silent, dryrun)
        if not new:
            ui.print_warning("path already exists: %s" % path)

        # run hooks if the path is new
        if new and self.setup_hook:
            ui.print_debug('setup hook')
            if not dryrun: self.run_hook(host, 'setup', tgt=path)



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
