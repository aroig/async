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
        self.keys_host = {}
        self.keys_wd = None



    def _get_uuid(self, hostn, dirn):
        if hostn in self.git_remotes:
            if dirn in self.git_remotes[hostn]['uuid']:
                return self.git_remotes[hostn]['uuid'][dirn]
        return None



    def _get_keys_in_host(self, host, uuid, silent=False, dryrun=False):
        """greps git-annex branch for all the keys in host. Faster than git-annex builtin
           because it does not perform individual location log queries"""

        # use cached value if we got one
        if uuid in self.keys_host:
            return self.keys_host[uuid]

        path = self.fullpath(host)
        key_re = re.compile('git-annex:.../.../(.*)\.log')

        try:
            raw = host.run_cmd("git grep --files-with-matches -e '1 %s' git-annex -- '*/*/*.log'" % uuid,
                               tgtpath=path, catchout=True).strip()

        except CmdError as err:
            return set()

        self.keys_host[uuid] = set([key for key in key_re.findall(raw)])
        return self.keys_host[uuid]



    def _get_keys_in_head(self, host, silent=False, dryrun=False):
        # use cached value if we got one
        if self.keys_wd:
            return self.keys_wd

        path = self.fullpath(host)
        path_re = re.compile('^([a-zA-Z0-9]+)\s*(.+)$', flags=re.MULTILINE)
        key_re = re.compile('^([a-zA-Z0-9]+)\s*blob.*\n(?:\.\./)*\.git/annex/objects/../../.*/(.+)$', flags=re.MULTILINE)
        try:
#   git ls-tree -r HEAD | cut -f 1 | grep -e "^120000" | cut -d " " -f 3 | git cat-file --batch
#               'sed s"|^\(\.\./\)*\.git/annex/objects/../../\(.*\)$|\2|;tx;d;:x" '
            raw = host.run_cmd('git ls-tree -r HEAD | grep -e "^120000" |cut -d " " -f 3-',
                               tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("couldn't retrieve keys: %s" % str(err))

        # this dictionary translates git objects to working tree paths for the
        # annexed files
        path_dic = {o: d.strip() for o, d in path_re.findall(raw)}

        try:
#   git ls-tree -r HEAD | cut -f 1 | grep -e "^120000" | cut -d " " -f 3 | git cat-file --batch
#               'sed s"|^\(\.\./\)*\.git/annex/objects/../../\(.*\)$|\2|;tx;d;:x" '
            raw = host.run_cmd('git cat-file --batch',
                               stdin='\n'.join(path_dic.keys()),
                               tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("couldn't retrieve keys: %s" % str(err))

        key_dic = {o: k.strip() for o, k in key_re.findall(raw)}

        if len(path_dic) != len(key_dic):
            raise SyncError("something odd happened in annex._get_keys_working_dir." + \
                            "path_dic and key_dic have different length")

        self.keys_wd = {key: path_dic.get(o, None) for o, key in key_dic.items()}
        return self.keys_wd



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



    def _init_annex(self, host, slow=False, silent=False, dryrun=False):
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



    def _push_annexed_files(self, local, remote, slow=False, silent=False, dryrun=False):
        annex_args = ['copy', '--quiet', '--fast', '--to=%s' % remote.name]
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        if slow: method = 'builtin'
        else:    method = 'grep'

        if not silent: ui.print_color("copying missing annexed files to remote")

        try:
            # get the missing files on the remote from local location log.
            # This is much slower than copy --from, since git-annex must go through the
            # location log. We can't stat to decide whether an annexed file is missing
            if method == 'builtin':
                ui.print_debug('git annex %s' % ' '.join(annex_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=silent)


            # Faster method to detect missing files on the remote. Essentially
            # we grep through the git-annex branch instead of checking the
            # location log one file at a time. However, we use a bit of internal
            # details on git-annex, and might break in the future.
            elif method == 'grep':
                uuid_local  = self._get_uuid(local.name, self.name)
                uuid_remote = self._get_uuid(remote.name, self.name)
                if uuid_local == None or uuid_remote == None:
                    raise SyncError("Can't find uuid for local and remote")

                keys_local = self._get_keys_in_host(local, uuid_local, silent=silent, dryrun=False)
                keys_remote = self._get_keys_in_host(local, uuid_remote, silent=silent, dryrun=False)
                keys_head = self._get_keys_in_head(local, silent=silent, dryrun=False)

                for key, d in keys_head.items():
                    if key in keys_local and not key in keys_remote:
                        ui.print_color('file: %s' % d)
                        ui.print_debug('git annex %s "%s"' % (' '.join(annex_args), d))
                        if not dryrun: cmd.annex(tgtdir=src, args=annex_args + [d], silent=silent)


            # run code on the remote to get the missing files.
            # We just check for broken symlinks. This is fast enough on SSD, but
            # not as fast as I'd like on usb disks aws instances...
            # I keep this for a while just in case, but I'll remove it eventually.
            elif method == 'remote':
                try:
                    raw = remote.run_cmd("find . -path './.git' -prune -or -type l -xtype l -print0",
                                         tgtpath=tgt, catchout=True)
                    missing = raw.split('\0')

                except CmdError as err:
                    raise SyncError("Failed to retrieve dangling symlinks on the remote")

                for key in missing:
                    if len(f.strip()) == 0: continue
                    ui.print_debug('git annex %s "%s"' % (' '.join(annex_args), key))
                    if not dryrun: cmd.annex(tgtdir=src, args=annex_args + [key], silent=silent)

        except subprocess.CalledProcessError as err:
            raise SyncError(str(err))



    def _pull_annexed_files(self, local, remote, slow=False, silent=False, dryrun=False):
        annex_args  = ['copy', '--quiet', '--fast', '--from=%s' % remote.name]
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        if slow: method = 'builtin'
        else:    method = 'grep'

        if not silent: ui.print_color("copying missing annexed files from remote")

        try:
            # This is quite fast, since git-annex stats the local annexed files
            # to check availability.
            if method == 'builtin':
                ui.print_debug('git annex %s' % ' '.join(annex_args))
                if not dryrun: cmd.annex(tgtdir=src, args=annex_args, silent=silent)

            # we grep the location log for keys. This is slower than the builtin,
            # but we can do something fun, print the file path being transferred!
            elif method == 'grep':
                uuid_local = self._get_uuid(local.name, self.name)
                uuid_remote = self._get_uuid(remote.name, self.name)
                if uuid_local == None or uuid_remote == None:
                    raise SyncError("Can't find uuid for local and remote")

                keys_local = self._get_keys_in_host(local, uuid_local, silent=silent, dryrun=False)
                keys_remote = self._get_keys_in_host(local, uuid_remote, silent=silent, dryrun=False)
                keys_head = self._get_keys_in_head(local, silent=silent, dryrun=False)

                for key, d in keys_head.items():
                    if key in keys_remote and not key in keys_local:
                        ui.print_color('file: %s' % d)
                        ui.print_debug('git annex %s "%s"' % (' '.join(annex_args), d))
                        if not dryrun: cmd.annex(tgtdir=src, args=annex_args + [d], silent=silent)

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



    def _annex_pre_sync_check(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        conflicts = self.get_conflicts(self, host)

        if len(conflicts) > 0:
            raise SyncError("There are unresolved conflicts in %s: \n%s" % (self.name, '\n'.join(conflicts)))


    def _annex_get_conflicts(self, host):
        path = self.fullpath(host)
        con_re = re.compile('^.*\.variant-[a-zA-Z0-9]+$', flags=re.MULTILINE)
        try:
            # catch conflicting files
            raw = host.run_cmd("find . -path './.git' -prune -or -path '*.variant-*' -print",
                               tgtpath=path, catchout=True).strip()

        except CmdError as err:
            raise SyncError(str(err))

        conflicts = con_re.findall(raw)
        return conflicts




    # Interface
    # ----------------------------------------------------------------

    def status(self, host, slow=False):
        status = super(AnnexDir, self).status(host, slow=slow)
        path = os.path.join(host.path, self.relpath)
        status['type'] = 'annex'

        # missing annexed files
        uuid = self._get_uuid(host.name, self.name)
        if uuid:
            keys_local = self._get_keys_in_host(host, uuid, silent=False, dryrun=False)
            keys_head = self._get_keys_in_head(host, silent=False, dryrun=False)
            status['missing'] = len(set(keys_head.keys()) - keys_local)
            status['unused']  = len(keys_local - set(keys_head.keys()))

        else:
            status['missing'] = -1

        # add conflicts in annex
        conflicts = self._annex_get_conflicts(host)
        status['conflicts'] = status['conflicts'] + len(conflicts)

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):
        # NOTE: We do not call git sync on parent class. annex does things his way

        # TODO: implement ignore
        # TODO: implement force to resolve merge conflicts

        if opts: slow = opts.slow
        else:    slow = False

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', silent=silent, dryrun=dryrun)
            self.run_hook(local, 'pre_sync_remote', silent=silent, dryrun=dryrun)

        #pre sync check
        self._annex_pre_sync_check(local, silent=silent, dryrun=dryrun)

        # sync & merge on remote
        self._annex_sync(local, remote, silent=silent, dryrun=dryrun)
        self._annex_merge(remote, silent=silent, dryrun=dryrun)

        # copy annexed files from the remote. This is fast as it uses mtimes
        if not opts.force == 'up' and self.name in local.annex_pull and self.name in remote.annex_push:
            self._pull_annexed_files(local, remote, slow=slow, silent=silent, dryrun=dryrun)

        # copy annexed files to the remote
        if not opts.force == 'down' and self.name in local.annex_push and self.name in remote.annex_pull:
            self._push_annexed_files(local, remote, slow=slow, silent=silent, dryrun=dryrun)

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
