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

from async.directories.git import GitDir
from async.directories.base import DirError, SyncError, InitError
from async.hosts.base import CmdError

import subprocess
import os
import re
import async.cmd as cmd
import async.archui as ui

class AnnexDir(GitDir):
    """Directory synced via git annex"""

    def __init__(self, conf):
        super(AnnexDir, self).__init__(conf)



    def _get_uuid(self, hostn, dirn):
        if hostn in self.git_remotes:
            if dirn in self.git_remotes[hostn]['uuid']:
                return self.git_remotes[hostn]['uuid'][dirn]
        return None



    def _get_keys_in_host(self, host, uuid, silent=False, dryrun=False):
        """greps git-annex branch for all the keys in host. Faster than git-annex builtin
           because it does not perform individual location log queries"""
        path = self.fullpath(host)
        git_args =['grep', '--files-with-matches', '-e', uuid, 'git-annex', '--', '*/*/*.log']
        key_re = re.compile('git-annex:.../.../(.*)\.log')

        try:
            raw = cmd.git(tgtdir=path, args=git_args, silent=silent, catchout=True).strip()

        except CmdError as err:
            raise SyncError("couldn't retrieve keys: %s" % str(err))

        L = []
        fail = []
        for key in raw.split('\n'):
            m = key_re.match(key)
            if m:  L.append(m.group(1))
            else:  fail.append(key)

        if len(fail) > 0:
            raise SyncError("Couldn't match %d keys on the location log:\n%s" % (len(fail), '\n'.join(fail)))

        return L



    def _get_keys_in_working_dir(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        try:
            cmd = 'git ls-tree -r HEAD | cut -f 1 | grep -e "^120000" | ' + \
               'cut -d " " -f 3 | git cat-file --batch | ' + \
               'sed s"|^\(\.\./\)*\.git/annex/objects/../../\(.*\)$|\2|;tx;d;:x" '
            raw = host.run_cmd(cmd, tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("couldn't retrieve keys: %s" % str(err))

        L = raw.strip().split('\n')
        return L



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

        # get the currently configured uuid
        cur_uuid = host.run_cmd('git config remote.%s.annex-uuid' % name,
                                tgtpath=path, catchout=True).strip()

        cur_url = host.run_cmd('git config remote.%s.url' % name,
                               tgtpath=path, catchout=True).strip()

        # update uuid only if missing and repo exists
        if len(cur_uuid) == 0 and len(cur_url) > 0:
            if not silent: ui.print_color("setting remote uuid for %s: %s" % (name, uuid))
            if not dryrun: host.run_cmd('git config remote.%s.annex-uuid "%s"' % (name, uuid), tgtpath=path)



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

            elif method == 'test':
                uuidA = self._get_uuid(local.name, self.name)
                uuidB = self._get_uuid(remote.name, self.name)

                if uuidA and uuidB:
                    keysA = set(self._get_keys_in_host(local, uuidA, silent=silent, dryrun=dryrun))
                    keysB = set(self._get_keys_in_host(local, uuidB, silent=silent, dryrun=dryrun))
                    # TODO: filter out whatever is not on the working dir

                    for f in keysA - keysB:
                        if len(f.strip()) == 0: continue
                        ui.print_debug('git annex %s "%s"' % (' '.join(annex_args), f))
                        if not dryrun: cmd.annex(tgtdir=src, args=annex_args + [f], silent=silent)
                else:
                    raise SyncError("Can't find uuid for local and remote")

            # run code on the remote to get the missing files.
            # We just check for broken symlinks. This is fast enough on SSD, but
            # not as fast as I'd like on usb disks aws instances...
            elif method == 'remote':
                try:
                    raw = remote.run_cmd("find . -path './.git' -prune -or -type l -xtype l -print0",
                                         tgtpath=tgt, catchout=True)
                    missing = raw.split('\0')

                except CmdError as err:
                    raise SyncError("Failed to retrieve dangling symlinks on the remote")

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
        path = os.path.join(host.path, self.relpath)
        status['type'] = 'annex'

        # missing annexed files
        try:
        # Painfully slow. When I manage to get the keys for the working tree fast, I'll be
        # in business to fix this.
#            raw = host.run_cmd("git annex find --not --in=here" ,tgtpath=path, catchout=True).strip()
#            if len(raw) == 0:    status['missing'] = 0
#            else:                status['missing'] = len(raw.split('\n'))

            status['missing'] = 0
        except:
            status['missing'] = -1

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):
        # NOTE: We do not call git sync on parent class. annex does things his way

        # TODO: implement ignore
        # TODO: implement force to resolve merge conflicts

        # pre-sync hook
        if runhooks:
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
        if runhooks:
            self.run_hook(local, 'post_sync', silent=silent, dryrun=dryrun)
            self.run_hook(local, 'post_sync_remote', silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_init', tgt=path, silent=silent, dryrun=dryrun)

        # NOTE: The parent initializes: git, hooks and remotes.
        super(AnnexDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # initialize annex
        if not host.path_exists(os.path.join(path, '.git/annex')):
            self._init_annex(host, silent=silent, dryrun=dryrun)

        # setup annex data on the remotes
        for k, r in self.git_remotes.items():
            # discard remotes named as the host
            if r['name'] == host.name: continue
            self._configure_annex_remote(host, r, silent=silent, dryrun=dryrun)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'check', tgt=path, silent=silent, dryrun=dryrun)

        # call check on the parent
        super(AnnexDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # run git annex fsck
        ui.print_debug('git annex fsck')
        try:
            if not silent: ui.print_color("checking annex")
            if not dryrun: host.run_cmd("git annex fsck", tgtpath=path)

        except CmdError as err:
            raise CheckError("git annex fsck failed: %s" % str(err))


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
