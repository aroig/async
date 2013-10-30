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
from async.hosts.base import CmdError

import subprocess
import os
import async.cmd as cmd
import async.archui as ui

class AnnexDir(BaseDir):
    """Directory synced via git annex"""
    def __init__(self, conf):
        super(AnnexDir, self).__init__(conf)
        self.annex_remotes = conf['annex_remotes']

        self.git_hooks_path = conf['conf_path']


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        # TODO: implement ignore
        # TODO: implement force
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        annex_sync_args = ['sync', remote.name]

        # I use quiet because git annex copy -to=... runs over all files and produces
        # too much output.
        # NOTE: git annex copy --to is much slower than copy --from, as it needs to
        # query the location log for each file, while --from just does stat.
        annex_get_args  = ['copy', '--quiet', '--fast', '--from=%s' % remote.name]
        annex_send_args = ['copy', '--quiet', '--fast', '--to=%s' % remote.name]

        # pre-sync hook
        ui.print_debug('pre_sync hook')
        if not dryrun: self.run_hook(local, 'pre_sync')

        # sync
        ui.print_debug('git annex %s' % ' '.join(annex_sync_args))
        try:
            if not dryrun: cmd.annex(tgtdir=src, args=annex_sync_args, silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        # merge remote working tree
        # TODO: if annex hooks work, this will be useless
        try:
            if not dryrun: remote.run_cmd("git annex merge", tgtpath=tgt)

        except CmdError as err:
            raise SyncError(str(err))

        # copy annexed files from the remote. This is fast as it uses mtimes

        if not opts.force == 'down' and self.name in local.annex_pull and self.name in remote.annex_push:
            try:
                if not silent: ui.print_color("copying missing annexed files from remote")
                ui.print_debug('git annex %s' % ' '.join(annex_get_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_get_args, silent=silent)

            except subprocess.CalledProcessError as err:
                raise SyncError(str(err))

        # copy annexed files to the remote
        if not opts.force == 'up' and self.name in local.annex_push and self.name in remote.annex_pull:
            if not silent: ui.print_color("copying missing annexed files to remote")

            # get a list of files with missing annex on the remote
            try:
                raw = remote.run_cmd("find -L . -type l -not -path './.git/*' -print0", tgtpath=tgt, catchout=True)
                missing = raw.split('\0')
            except CmdError as err:
                missing = None

            try:
                # this is faster, but may miss annexed files not linked in the working dir
                # TODO: check whether the remote is in direct mode.
                if missing != None and not opts.slow:
                    for f in missing:
                        if len(f.strip()) == 0: continue
                        ui.print_debug('git annex %s "%s"' % (' '.join(annex_send_args), f))
                        if not dryrun: cmd.annex(tgtdir=src, args=annex_send_args + [f], silent=silent)

                # this may take some time as it must check the location log for every file
                else:
                    ui.print_debug('git annex %s' % ' '.join(annex_send_args))
                    if not dryrun: cmd.annex(tgtdir=src, args=annex_send_args, silent=silent)

            except subprocess.CalledProcessError as err:
                raise SyncError(str(err))

        # post-sync hook
        ui.print_debug('post_sync hook')
        if not dryrun: self.run_hook(local, 'post_sync')



    def setup(self, host, silent=False, dryrun=False, opts=None):
        # TODO: finish repo initialization
        path = self.fullpath(host)

        # create directory and run hooks
        super(AnnexDir, self).setup(host, silent, dryrun, opts)

        # initialize git
        if not host.path_exists(os.path.join(path, '.git')):
            if not silent: ui.print_color("Initializing git repo")
            try:
                if not dryrun: host.run_cmd('git init', tgtpath=path)

            except CmdError as err:
                ui.print_error("git init failed: %s" % str(err))
                return

        # initialize annex
        if not host.path_exists(os.path.join(path, '.git/annex')):
            annex_desc = "%s : %s" % (host.name, self.name)
            if not silent: ui.print_color("Initializing annex")
            try:
                if not dryrun: host.run_cmd('git annex init "%s"' % annex_desc, tgtpath=path)

            except CmdError as err:
                ui.print_error("git annex init failed: %s" % str(err))
                return

        # setup remotes
        remotes_raw = host.run_cmd('git remote show', tgtpath=path, catchout=True)
        remotes = set([r.strip() for r in remotes_raw.split('\n') if len(r.strip()) > 0])
        for k, r in self.annex_remotes.items():
            name = r['name']
            url = r['url'].replace('%d', self.relpath)

            # discard remotes named as the host
            if name == host.name: continue

            if not name in remotes:
                if not silent: ui.print_color("Adding remote '%s'" % name)
                try:
                    if not dryrun: host.run_cmd('git remote add "%s" "%s"' % (name, url), tgtpath=path)
                except CmdError as err:
                    ui.print_error("git remote add failed: %s" % str(err))

        # setup hooks
        for h, p in r['git_hooks'].items():
            srcpath = os.path.join(self.git_hooks_path, p)
            tgtpath = os.path.join(path, '.git/hooks', h)

            with open(srcpath, 'r') as fd:
                script = fd.read()

            if not silent: ui.print_color("Updating git hook '%s'" % h)
            try:
                if not dryrun: host.run_cmd('cat > "%s"; chmod +x "%s"' % (tgtpath, tgtpath),
                                            tgtpath=path, stdin=script)

            except CmdError as err:
                ui.print_error("hook setup failed: %s" % str(err))



    def check(self, local, silent=False, dryrun=False, opts=None):
        src = self.fullpath(local)

        # check
        ui.print_debug('git annex fsck')
        try:
            if not silent: ui.print_color("Performing annex fsck")
            if not dryrun: local.run_cmd("git annex fsck", tgtpath=src)

        except CmdError as err:
            ui.print_error(str(err))




# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
