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

from async.directories.base import BaseDir, DirError, SyncError, InitError
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


    def _get_uuid(self, hostn, dirn):
        if hostn in self.annex_remotes:
            if dirn in self.annex_remotes[hostn]['uuid']:
                return self.annex_remotes[hostn]['uuid'][dirn]
        return None


    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        super(AnnexDir, self).sync(local, remote, silent=silent, dryrun=dryrun, opts=opts)

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
        self.run_hook(local, 'pre_sync', silent=silent, dryrun=dryrun)
        self.run_hook(local, 'pre_sync_remote', silent=silent, dryrun=dryrun)

        # sync
        ui.print_debug('git annex %s' % ' '.join(annex_sync_args))
        try:
            if not dryrun: cmd.annex(tgtdir=src, args=annex_sync_args, silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))

        # merge remote working tree
        try:
            if not dryrun: remote.run_cmd("git annex merge", tgtpath=tgt)

        except CmdError as err:
            raise SyncError(str(err))

        # copy annexed files from the remote. This is fast as it uses mtimes
        if not opts.force == 'up' and self.name in local.annex_pull and self.name in remote.annex_push:
            try:
                if not silent: ui.print_color("copying missing annexed files from remote")
                ui.print_debug('git annex %s' % ' '.join(annex_get_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_get_args, silent=silent)

            except subprocess.CalledProcessError as err:
                raise SyncError(str(err))

        # copy annexed files to the remote
        if not opts.force == 'down' and self.name in local.annex_push and self.name in remote.annex_pull:
            if not silent: ui.print_color("copying missing annexed files to remote")

            # get a list of files with missing annex on the remote. we just check for broken symlinks.
            # This is fast enough on SSD, but not as fast as I'd like on usb disks...
            try:
                raw = remote.run_cmd("find . -path './.git' -prune -or -type l -xtype l -print0",
                                     tgtpath=tgt, catchout=True)
                missing = raw.split('\0')
            except CmdError as err:
                missing = None

            try:
                # This is faster than 'copy --from', but misses annexed files not linked in the working dir
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
        self.run_hook(local, 'post_sync', silent=silent, dryrun=dryrun)
        self.run_hook(local, 'post_sync_remote', silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None):
        super(AnnexDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts)
        path = self.fullpath(host)

        # initialize git
        if not host.path_exists(os.path.join(path, '.git')):
            if not silent: ui.print_color("initializing git repo")
            try:
                if not dryrun: host.run_cmd('git init', tgtpath=path)

            except CmdError as err:
                raise InitError("git init failed: %s" % str(err))

        # initialize annex
        if not host.path_exists(os.path.join(path, '.git/annex')):
            annex_desc = "%s : %s" % (host.name, self.name)
            if not silent: ui.print_color("initializing annex")
            try:
                # set the uuid if we know it
                uuid = self._get_uuid(host.name, self.name)
                if uuid:
                    if not silent: ui.print_color("setting repo uuid: %s" % uuid)
                    if not dryrun: host.run_cmd('git config annex.uuid "%s"' % uuid, tgtpath=path)

                if not dryrun: host.run_cmd('git annex init "%s"' % annex_desc, tgtpath=path)

            except CmdError as err:
                raise InitError("git annex init failed: %s" % str(err))

        # setup remotes
        remotes_raw = host.run_cmd('git remote show', tgtpath=path, catchout=True)
        remotes = set([r.strip() for r in remotes_raw.split('\n') if len(r.strip()) > 0])
        for k, r in self.annex_remotes.items():
            name = r['name']
            url = r['url'].replace('%d', self.relpath)

            # discard remotes named as the host
            if name == host.name: continue

            # get the uuid
            if 'uuid' in r: uuid = r['uuid'].get(self.name, None)
            else:           uuid = None

            if uuid == None:
                ui.print_warning("no configured uuid for remote %s. skipping" % name)
                continue

            if not name in remotes:
                if not silent: ui.print_color("adding remote '%s'" % name)
                try:
                    if not dryrun: host.run_cmd('git remote add "%s" "%s"' % (name, url), tgtpath=path)

                except CmdError as err:
                    raise InitError("git remote add failed: %s" % str(err))

            # set remote config
            if uuid:
                if not silent: ui.print_color("setting remote uuid for %s: %s" % (name, uuid))
                if not dryrun: host.run_cmd('git config remote.%s.annex-uuid "%s"' % (name, uuid), tgtpath=path)


        # setup hooks
        remote = self.annex_remotes.get(host.name, None)
        if remote and 'git_hooks' in remote and self.name in remote['git_hooks']:
            hooks = remote['git_hooks'][self.name]

            for h, p in hooks.items():
                srcpath = os.path.join(self.git_hooks_path, p)
                tgtpath = os.path.join(path, '.git/hooks', h)

                try:
                    with open(srcpath, 'r') as fd:
                        script = fd.read()
                        if not silent: ui.print_color("updating git hook '%s'" % h)
                        if not dryrun: host.run_cmd('cat > "%s"; chmod +x "%s"' % (tgtpath, tgtpath),
                                                    tgtpath=path, stdin=script)

                except CmdError as err:
                    raise InitError("hook setup failed: %s" % str(err))

                except IOError as err:
                    raise InitError("hook setup failed: %s" % str(err))

        # run hooks
        self.run_hook(host, 'init', tgt=path, silent=silent, dryrun=dryrun)




    def check(self, host, silent=False, dryrun=False, opts=None):
        super(AnnexDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts)
        path = self.fullpath(host)

        # run git annex fsck
        ui.print_debug('git annex fsck')
        try:
            if not silent: ui.print_color("checking annex")
            if not dryrun: host.run_cmd("git annex fsck", tgtpath=path)

        except CmdError as err:
            raise CheckError("git annex fsck failed: %s" % str(err))



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
