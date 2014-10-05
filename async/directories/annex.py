#!/usr/bin/env python
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
from async.directories.base import DirError, SyncError, InitError, CheckError
from async.hosts.base import CmdError

import subprocess
import os
import re
import async.cmd as cmd
import async.archui as ui

class AnnexDir(GitDir):
    """Directory synced via git annex"""
    quotes_re = re.compile('^"(.*)"$')

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

        loclog_re = re.compile('^git-annex:.../.../(.*)\.log:([0-9.]*)s\s*([0-9]).*$', flags=re.MULTILINE)

        # use cached value if we got one
        if uuid in self.keys_host:
            return self.keys_host[uuid]

        path = self.fullpath(host)

        try:
            raw = host.run_cmd("git grep -e '%s' git-annex -- '*/*/*.log'" % uuid,
                               tgtpath=path, catchout=True).strip()

        except CmdError as err:
            return set()

        keydict = {}
        for key, mtime, state in loclog_re.findall(raw):
            mtime = float(mtime)
            state = int(state)
            if not key in keydict:
                keydict[key] = (mtime, state)
            else:
                t, s = keydict[key]
                if mtime > t: keydict[key] = (mtime, state)

        self.keys_host[uuid] = set([key for key, st in keydict.items() if st[1] == 1])
        return self.keys_host[uuid]



    def _get_keys_in_head(self, host, silent=False, dryrun=False):
        # use cached value if we got one
        if self.keys_wd:
            return self.keys_wd

        path = self.fullpath(host)
        path_re = re.compile('^120000 blob ([a-zA-Z0-9]+)\s*(.+)$', flags=re.MULTILINE)
        key_re = re.compile('^([a-zA-Z0-9]+)\s*blob.*\n(?:\.\./)*\.git/annex/objects/../../.*/(.+)$', flags=re.MULTILINE)
        try:
            # I use -z to prevent git from escaping the string when there are accented characters in filename
            raw = host.run_cmd('git ls-tree -r -z HEAD | grep -zZ -e "^120000" | sed "s/\\x00/\\n/g"',
                               tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("can't retrieve annex keys. %s" % str(err))


        # this dictionary translates git objects to working tree paths for the
        # symlinks in the working dir. May be annexed files, or just commited symlinks.
        path_dic = {o: d.strip() for o, d in path_re.findall(raw)}

        try:
            raw = host.run_cmd('git cat-file --batch',
                               stdin='\n'.join(path_dic.keys()),
                               tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("can't retrieve annex keys. %s" % str(err))

        # this dictionary translates git objects to git annex keys used to identify annexed files.
        key_dic = {o: k.strip() for o, k in key_re.findall(raw)}


        self.keys_wd = {}
        for o, key in key_dic.items():

            if o in path_dic:
                self.keys_wd[key] = path_dic[o]

            else:
                raise SyncError("something odd happened in annex._get_keys_working_dir. " + \
                            "Found a git object in key_dic not in path_dic.")

        return self.keys_wd



    def _configure_annex_remote(self, host, rmt, silent=False, dryrun=False):
        path = self.fullpath(host)
        name = rmt['name']

        # get the uuid for current host from config
        if 'uuid' in rmt: uuid = rmt['uuid'].get(self.name, None)
        else:             uuid = None

        if uuid == None:
            ui.print_warning("no configured uuid for remote %s. skipping" % name)
            return

        # get the currently configured uuid
        try:
            cur_uuid = host.run_cmd('git config remote.%s.annex-uuid' % name,
                                    tgtpath=path, catchout=True).strip()
        except CmdError:
            cur_uuid = ""

        try:
            cur_url = host.run_cmd('git config remote.%s.url' % name,
                                   tgtpath=path, catchout=True).strip()

        except CmdError:
            cur_url = ""

        # update uuid only if missing and repo exists
        if len(cur_uuid) == 0 and len(cur_url) > 0:
            if not silent: ui.print_color("setting remote uuid for %s: %s" % (name, uuid))
            if not dryrun:
                host.run_cmd('git config remote.%s.annex-uuid "%s"' % (name, uuid), tgtpath=path, silent=silent)



    def _init_annex(self, host, slow=False, silent=False, dryrun=False):
        path = self.fullpath(host)
        annex_desc = "%s : %s" % (host.name, self.name)
        if not silent: ui.print_color("initializing annex")
        try:
            # set the uuid if we know it
            uuid = self._get_uuid(host.name, self.name)
            if uuid:
                if not silent: ui.print_color("setting repo uuid: %s" % uuid)
                if not dryrun:
                    host.run_cmd('git config annex.uuid "%s"' % uuid, tgtpath=path, silent=silent)

            if not dryrun:
                host.run_cmd('git annex init "%s"' % annex_desc, tgtpath=path, silent=silent)

        except CmdError as err:
            raise InitError("git annex initialization failed. %s" % str(err))



    def _push_annexed_files(self, local, remote, slow=False, silent=False, dryrun=False):
        annex_cmd = ["git",  "annex",  "copy", "--quiet",  "--fast",  "--to=%s" % remote.name]
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
                ui.print_debug(' '.join(annex_cmd))
                if not dryrun: local.run_cmd(annex_cmd, tgtpath=src, silent=silent)


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
                        ui.print_color('%s' % d)
                        ui.print_debug('%s "%s"' % (' '.join(annex_cmd), d))
                        if not dryrun: local.run_cmd(annex_cmd + [d], tgtpath=src, silent=silent)


            # run code on the remote to get the missing files.
            # We just check for broken symlinks. This is fast enough on SSD, but
            # not as fast as I'd like on usb disks aws instances...
            # I keep this for a while just in case, but I'll remove it eventually.
            elif method == 'remote':
                raw = remote.run_cmd("find . -path './.git' -prune -or -type l -xtype l -print0",
                                     tgtpath=tgt, catchout=True)
                missing = raw.split('\0')

                for key in missing:
                    if len(f.strip()) == 0: continue
                    ui.print_debug('%s "%s"' % (' '.join(annex_cmd), key))
                    if not dryrun: local.run_cmd(annex_cmd + [key], tgtpath=src, silent=silent)

        except CmdError as err:
            raise SyncError("push annexed files failed. %s" % str(err))



    def _pull_annexed_files(self, local, remote, slow=False, silent=False, dryrun=False):
        annex_cmd  = ['git', 'annex', 'copy', '--quiet', '--fast', '--from=%s' % remote.name]
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        if slow: method = 'builtin'
        else:    method = 'grep'

        if not silent: ui.print_color("copying missing annexed files from remote")

        try:
            # This is quite fast, since git-annex stats the local annexed files
            # to check availability.
            if method == 'builtin':
                ui.print_debug(' '.join(annex_cmd))
                if not dryrun: local.run_cmd(annex_cmd, tgtpath=src, silent=silent)

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
                        ui.print_color('%s' % d)
                        ui.print_debug('%s "%s"' % (' '.join(annex_cmd), d))
                        if not dryrun: local.run_cmd(annex_cmd + [d], tgtpath=src, silent=silent)

        except CmdError as err:
            raise SyncError("pull annexed files failed. %s" % str(err))



    def _annex_sync(self, local, remote, set_origin=True, silent=False, dryrun=False, batch=False, force=None):
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        branch = self._git_current_branch(local)
        remote_branch = self._git_current_branch(remote)

        if branch != remote_branch:
            SyncError("Remote branch %s is different from local branch %s" %
                      (remote_branch, branch))

        if not silent: ui.print_color("checking local repo")
        if not self.is_clean(local):
            SyncError("Local working directory is not clean")

        try:
            # fetch from remote
            if not silent: ui.print_color("fetching from %s" % remote.name)
            if not dryrun: local.run_cmd('git fetch "%s"' % remote.name,
                                         tgtpath=src, silent=silent)

            # set current branch origin if it exists on the remote
            if set_origin and self._git_ref_exists(local, 'refs/remotes/%s/%s' % (remote.name, branch)):
                if not silent: ui.print_color("setting current branch origin")
                if not dryrun: local.run_cmd('git branch -u %s/%s' % (remote.name, branch),
                                             tgtpath=src, silent=silent)

            # sync git annex
            if not dryrun: local.run_cmd('git annex sync %s' % remote.name,
                                         tgtpath=src, silent=silent)

            # do a merge on the remote if the branches match
            if remote_branch == branch:
                if not dryrun: remote.run_cmd("git annex merge",
                                              tgtpath=tgt, silent=silent)
            else:
                raise SyncError("Remote branch %s is different from local branch %s" %
                                (remote_branch, branch))


        except CmdError as err:
            raise SyncError(str(err))


    def _annex_sync_files(self, local, remote, set_origin=True, silent=False, dryrun=False, batch=False, force=None, slow=False):
        # copy annexed files from the remote. This is fast as it uses mtimes
        if not force == 'up' and self.name in local.annex_pull and self.name in remote.annex_push:
            self._pull_annexed_files(local, remote, slow=slow, silent=silent, dryrun=dryrun)

        # copy annexed files to the remote
        if not force == 'down' and self.name in local.annex_push and self.name in remote.annex_pull:
            self._push_annexed_files(local, remote, slow=slow, silent=silent, dryrun=dryrun)



    def _annex_pre_sync_check(self, host, silent=False, dryrun=False):

        self._git_pre_sync_check(host, silent=silent, dryrun=dryrun)

        path = self.fullpath(host)
        conflicts = self._annex_get_conflicts(host)
        if len(conflicts) > 0:
            raise SyncError("There are unresolved annex conflicts in %s: \n%s" % (self.name, '\n'.join(conflicts)))



    def _annex_post_sync_check(self, host, silent=False, dryrun=False):

        self._git_post_sync_check(host, silent=silent, dryrun=dryrun)

        path = self.fullpath(host)
        conflicts = self._annex_get_conflicts(host)

        if len(conflicts) > 0:
            raise SyncError("There are unresolved annex conflicts in %s: \n%s" % (self.name, '\n'.join(conflicts)))



    def _annex_get_conflicts(self, host):
        path = self.fullpath(host)
        con_re = re.compile('^.*\.variant-[a-zA-Z0-9]+$', flags=re.MULTILINE)
        try:
            # catch conflicting files
            raw = host.run_cmd("find . -path './.git' -prune -or -path '*.variant-*' -print",
                               tgtpath=path, catchout=True).strip()

        except CmdError as err:
            raise SyncError("annex_get_conflicts failed. %s" % str(err))

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

        if opts:
            slow = opts.slow
            batch = opts.batch
            force = opts.force
        else:
            slow = False
            batch = False
            force = None

        # initialize local directory if needed
        if not self.is_initialized(local):
            self.init(local, silent=silent, dryrun=dryrun, opts=opts)

        # initialize remote directory if needed
        if not self.is_initialized(remote):
            self.init(remote, silent=silent, dryrun=dryrun, opts=opts)

        # do basic checks
        self.check_paths(local)
        self.check_paths(remote)

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'pre_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)

        # pre sync check
        self._annex_pre_sync_check(local, silent=silent, dryrun=dryrun)

        # sync
        self._annex_sync(local, remote, set_origin=True, silent=silent, dryrun=dryrun,
                         batch=batch, force=force)

        # post sync check
        self._annex_post_sync_check(local, silent=silent, dryrun=dryrun)

        # sync annexed files
        self._annex_sync_files(local, remote, silent=silent, dryrun=dryrun,
                               batch=batch, force=force, slow=slow)

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'post_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_init', tgt=path, silent=silent, dryrun=dryrun)

        # TODO: mark dead remotes as dead in annex

        # NOTE: The parent initializes: git, hooks and remotes.
        super(AnnexDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # initialize annex
        if not host.path_exists(os.path.join(path, '.git/annex')):
            self._init_annex(host, silent=silent, dryrun=dryrun)

        # setup annex data on the remotes
        for k, r in self.git_remotes.items():

            # discard remotes named as the host or dead
            if r['name'] == host.name or r['dead']: continue

            self._configure_annex_remote(host, r, silent=silent, dryrun=dryrun)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        if opts: slow = opts.slow
        else:    slow = False

        # do basic checks
        self.check_paths(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_check', tgt=path, silent=silent, dryrun=dryrun)

        # call check on the parent
        super(AnnexDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # run git annex fsck
        try:
            if not silent: ui.print_color("checking annex")
            ui.print_debug('git annex fsck')
            if not dryrun:
                if slow:
                    host.run_cmd("git annex fsck", tgtpath=path, silent=silent)
                else:
                    host.run_cmd("git annex fsck --fast -q", tgtpath=path, silent=silent)

        except CmdError as err:
            raise CheckError("git annex fsck failed. %s" % str(err))

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_check', tgt=path, silent=silent, dryrun=dryrun)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
