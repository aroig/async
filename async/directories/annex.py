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


    def _init_git(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        if not silent: ui.print_color("initializing git repo")
        try:
            if not dryrun: host.run_cmd('git init', tgtpath=path)

        except CmdError as err:
            raise InitError("git init failed: %s" % str(err))


    def _init_annex(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
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



    def _configure_annex_remote(self, host, rmt, silent=False, dryrun=False):
        path = self.fullpath(host)
        name = rmt['name']
        url = rmt['url'].replace('%d', self.relpath)

        # get the uuid for current host from config
        if 'uuid' in rmt: uuid = rmt['uuid'].get(self.name, None)
        else:             uuid = None

        if uuid == None:
            ui.print_warning("no configured uuid for remote %s. skipping" % name)
            return

        # get the actual uuid and url
        cur_uuid = host.run_cmd('git config remote.%s.annex-uuid' % name,
                                tgtpath=path, catchout=True).strip()

        cur_url = host.run_cmd('git config remote.%s.url' % name,
                               tgtpath=path, catchout=True).strip()

        # add repo if not configured
        if len(cur_url) == 0:
            if not silent: ui.print_color("adding remote '%s'" % name)
            try:
                if not dryrun: host.run_cmd('git remote add "%s" "%s"' % (name, url), tgtpath=path)

            except CmdError as err:
                raise InitError("git remote add failed: %s" % str(err))

        # update uuid only if missing
        if len(cur_uuid) == 0:
            if not silent: ui.print_color("setting remote uuid for %s: %s" % (name, uuid))
            if not dryrun: host.run_cmd('git config remote.%s.annex-uuid "%s"' % (name, uuid), tgtpath=path)



    def _configure_annex_hook(self, host, hook, hook_path, silent=False, dryrun=False):
        path = self.fullpath(host)
        srcpath = os.path.join(self.git_hooks_path, hook_path)
        tgtpath = os.path.join(path, '.git/hooks', hook)

        try:
            with open(srcpath, 'r') as fd:
                script = fd.read()
                if not silent: ui.print_color("updating git hook '%s'" % hook)
                if not dryrun: host.run_cmd('cat > "%s"; chmod +x "%s"' % (tgtpath, tgtpath),
                                            tgtpath=path, stdin=script)

        except CmdError as err:
            raise InitError("hook setup failed: %s" % str(err))

        except IOError as err:
            raise InitError("hook setup failed: %s" % str(err))



    def _push_annexed_files(self, local, remote, method='local', silent=False, dryrun=False):
        annex_args = ['copy', '--quiet', '--fast', '--to=%s' % remote.name]
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        if not silent: ui.print_color("copying missing annexed files to remote")

        try:
            # get the missing files on the remote from local location log.
            # This is much slower than copy --from, since git-annex must go through the
            # location log. We can't stat to decide whether an annexed file is missing
            if method == 'local':
                ui.print_debug('git annex %s' % ' '.join(annex_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=silent)


            # run code on the remote to get the missing files.
            # We just check for broken symlinks. This is fast enough on SSD, but
            # not as fast as I'd like on usb disks aws instances...
            elif method == 'remote':
                try:
                    raw = remote.run_cmd("find . -path './.git' -prune -or -type l -xtype l -print0",
                                         tgtpath=tgt, catchout=True)
                    missing = raw.split('\0')

                except CmdError as err:
                    missing = []

                for f in missing:
                    if len(f.strip()) == 0: continue
                    ui.print_debug('git annex %s "%s"' % (' '.join(annex_args), f))
                    if not dryrun: cmd.annex(tgtdir=src, args=annex_args + [f], silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))



    def _pull_annexed_files(self, local, remote, method='local', silent=False, dryrun=False):
        annex_args  = ['copy', '--quiet', '--fast', '--from=%s' % remote.name]
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        try:
            if method == 'local':
                if not silent: ui.print_color("copying missing annexed files from remote")
                ui.print_debug('git annex %s' % ' '.join(annex_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))



    def _annex_sync(self, local, remote, silent=False, dryrun=False):
        annex_args = ['sync', remote.name]
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        ui.print_debug('git annex %s' % ' '.join(annex_args))
        try:
            if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))


    def _annex_merge(self, host, silent=False, dryrun=False):
        """ do an annex merge on the host """
        path = self.fullpath(host)
        try:
            if not dryrun: host.run_cmd("git annex merge", tgtpath=path)

        except CmdError as err:
            raise SyncError(str(err))



    # Interface
    # ----------------------------------------------------------------
    def status(self, host):
        status = super(AnnexDir, self).status(host)
        status['type'] = 'annex'
        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        super(AnnexDir, self).sync(local, remote, silent=silent, dryrun=dryrun, opts=opts)
        # TODO: implement ignore
        # TODO: implement force to resolve merge conflicts

        # pre-sync hook
        self.run_hook(local, 'pre_sync', silent=silent, dryrun=dryrun)
        self.run_hook(local, 'pre_sync_remote', silent=silent, dryrun=dryrun)

        # sync & merge on remote
        self._annex_sync(local, remote, silent=silent, dryrun=dryrun)
        self._annex_merge(remote, silent=silent, dryrun=dryrun)

        # copy annexed files from the remote. This is fast as it uses mtimes
        if not opts.force == 'up' and self.name in local.annex_pull and self.name in remote.annex_push:
            self._pull_annexed_files(local, remote, method='local', silent=silent, dryrun=dryrun)

        # copy annexed files to the remote
        if not opts.force == 'down' and self.name in local.annex_push and self.name in remote.annex_pull:
            self._push_annexed_files(local, remote, method='local', silent=silent, dryrun=dryrun)

        # post-sync hook
        self.run_hook(local, 'post_sync', silent=silent, dryrun=dryrun)
        self.run_hook(local, 'post_sync_remote', silent=silent, dryrun=dryrun)




    def init(self, host, silent=False, dryrun=False, opts=None):
        super(AnnexDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts)
        path = self.fullpath(host)

        # initialize git
        if not host.path_exists(os.path.join(path, '.git')):
            self._init_git(host, silent=silent, dryrun=dryrun)

        # initialize annex
        if not host.path_exists(os.path.join(path, '.git/annex')):
            self._init_annex(host, silent=silent, dryrun=dryrun)

        # setup remotes
        for k, r in self.annex_remotes.items():
            # discard remotes named as the host
            if r['name'] == host.name: continue

            self._configure_annex_remote(host, r, silent=silent, dryrun=dryrun)

        # setup hooks
        remote = self.annex_remotes.get(host.name, None)
        if remote and 'git_hooks' in remote and self.name in remote['git_hooks']:
            hooks = remote['git_hooks'][self.name]
            for h, p in hooks.items():
                self._configure_annex_hook(host, h, p, silent=silent, dryrun=dryrun)

        # run async hooks
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
