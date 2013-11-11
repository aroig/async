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

import os
import subprocess

from async.directories.base import BaseDir, DirError, SyncError, InitError, HookError
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
    def status(self, host, slow=False):
        status = super(UnisonDir, self).status(host, slow=slow)
        path = os.path.join(host.path, self.relpath)
        status['type'] = 'unison'

        # number of files
        if slow:
            try:
                raw = host.run_cmd("find . -not -type d -and -print | wc -l",
                               tgtpath=path, catchout=True).strip()
                status['numfiles'] = int(raw)
            except:
                status['numfiles'] = -1

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):
        src = '%s/' % local.path

        # get the target dir
        if isinstance(remote, SshHost):
            tgt = 'ssh://%s@%s/%s/' % (remote.user, remote.hostname, remote.path)
            tgtalias = 'ssh://%s/%s/' % (remote.name, remote.path)

        elif isinstance(remote, DirectoryHost):
            tgt = remote.path
            tgtalias = remote.path

        else:
            raise DirError("Unsuported type %s for remote directory %s" % (remote.type, self.relpath))

        # prepare args
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

        # get the ignores
        ignore = set(self.ignore) | set(opts.ignore) | set(local.ignore) | set(remote.ignore)
        for p in ignore:
            args = args + ['-ignore', 'Path %s' % p]

        # prepare other options
        if opts.auto:  args = args + ['-auto']
        if opts.slow:  args = args + ['-fastcheck' 'false']
        if opts.batch: args = args + ['-batch']

        if opts.force == 'up':   args = args + ['-force', src]
        if opts.force == 'down': args = args + ['-force', tgt]

        if len(sshargs) > 0:     args = args + ['-sshargs', ' '.join(sshargs)]

        args = args + [self.unison_profile]

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'pre_sync_remote', silent=silent, dryrun=dryrun)

        # call sync on the parent
        super(UnisonDir, self).sync(local, remote, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # sync
        ui.print_debug('unison %s' % ' '.join(args))
        try:
            if not dryrun: cmd.unison(args=args, silent=silent)
        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'post_sync_remote', silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_init', tgt=path, silent=silent, dryrun=dryrun)

        super(UnisonDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'check', tgt=path, silent=silent, dryrun=dryrun)

        super(UnisonDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
