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
import async.archui as ui

class UnisonDir(BaseDir):

    def __init__(self, basepath, conf):
        super(UnisonDir, self).__init__(basepath, conf)


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, opts):
        src = local.path

        if remote.type == 'ssh':
            tgt = 'ssh://%s@%s/%s/' % (remote.user, remote.hostname, remote.path))
            tgtalias = 'ssh://%s/%s/' % (remote.name, remote.path)
        else:
            tgt = remote.path
            tgtalias = remote.path

        sshargs = []

        if remote.ssh_trust:
            sshargs = sshargs + ['-o LogLevel=quiet',
                                 '-o UserKnownHostsFile=/dev/null',
                                 '-o StrictHostKeyChecking=no']

        if remote.ssh_key: sshargs = sshargs + ['-i', remote.ssh_key]

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

        ui.print_debug('unison %s' % ' '.join(args))
        cmd.unison(args=args, silent=False)



    def setup(self, host, opts):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
