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

from async.directories.base import BaseDir, DirError, SyncError, InitError, CheckError
from async.hosts.base import CmdError

import subprocess
import os
import re
import async.cmd as cmd
import async.archui as ui

class GitDir(BaseDir):
    """Directory synced via git"""

    def __init__(self, conf):
        super(GitDir, self).__init__(conf)

        self.git_hooks_dir = conf['githooks_dir']   # if set, symlinks hooks to this directory
        self.git_remotes = conf['git_remotes']
        self.git_hooks_conf = conf['conf_path']



    def _init_git(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        if not silent: ui.print_color("initializing git repo")
        try:
            if not dryrun:
                host.run_cmd('git init', tgtpath=path, silent=silent)

        except CmdError as err:
            raise InitError("git init failed. %s" % str(err))



    def _configure_git_remote(self, host, rmt, silent=False, dryrun=False):
        path = self.fullpath(host)
        name = rmt['name']
        url = rmt['url'].replace('%d', self.relpath)

        # if remote is dead, we are done
        if rmt['dead']: return

        # get currently configured url for the remote
        try:
            cur_url = host.run_cmd('git config remote.%s.url' % name,
                                   tgtpath=path, catchout=True).strip()
        except CmdError:
            cur_url = ""


        # add remote if not configured
        if len(cur_url) == 0:
            if not silent: ui.print_color("adding remote '%s'" % name)
            try:
                if not dryrun:
                    host.run_cmd('git remote add "%s" "%s"' % (name, url), tgtpath=path, silent=silent)

            except CmdError as err:
                raise InitError("git remote add failed. %s" % str(err))

        # update url if changed
        elif len(cur_url) > 0 and cur_url != url:
            if not silent: ui.print_color("updating url for remote '%s'" % name)
            try:
                if not dryrun:
                    host.run_cmd('git remote set-url "%s" "%s"' % (name, url), tgtpath=path, silent=silent)

            except CmdError as err:
                raise InitError("git remote set-url failed. %s" % str(err))



    def _remove_git_remote(self, host, rmt, silent=False, dryrun=False):
        path = self.fullpath(host)
        name = rmt['name']

        # get currently configured url for the remote
        try:
            cur_url = host.run_cmd('git config remote.%s.url' % name,
                                   tgtpath=path, catchout=True).strip()
        except CmdError:
            cur_url = ""

        # if remote exists and is dead, remove it
        if len(cur_url) > 0 and rmt['dead']:
            if not silent: ui.print_color("removing remote '%s'" % name)
            try:
                if not dryrun:
                    host.run_cmd('git remote remove "%s"' % name, tgtpath=path, silent=silent)

            except CmdError as err:
                raise InitError("git remote remove failed. %s" % str(err))



    def _configure_git_hook(self, host, hook, hook_path, silent=False, dryrun=False):
        path = self.fullpath(host)
        srcpath = os.path.join(self.git_hooks_conf, hook_path)
        tgtpath = os.path.join(path, '.git/hooks', hook)

        try:
            with open(srcpath, 'r') as fd:
                script = fd.read()
                if not silent: ui.print_color("updating git hook '%s'" % hook)
                if not dryrun:
                    host.run_cmd('cat > "%s"; chmod +x "%s"' % (tgtpath, tgtpath),
                                 tgtpath=path, stdin=script, silent=silent)

        except CmdError as err:
            raise InitError("configuration of git hook failed. %s" % str(err))

        except IOError as err:
            raise InitError("hook setup failed: %s" % str(err))



    def _git_pre_sync_check(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        try:
            raw = host.run_cmd("find . -path './.git' -prune -or -print | grep '\.git/' | wc -l",
                               tgtpath=path, catchout=True)
            if int(raw) > 0:
                ui.print_warning("directory %s on %s contains a nested git repo. It will be ignored." % (self.name, host.name))

        except CmdError as err:
            raise SyncError("git pre sync check failed. %s" % str(err))



    def _git_post_sync_check(self, host, silent=False, dryrun=False):
        st = self._parse_git_status(host)

        if len(st['conflicts']) > 0:
            raise SyncError("git post sync check failed: Conflicts detected")

        elif (len(st['staged']) + len(st['changed']) + len(st['deleted']) +
             len(st['untracked']) + len(st['unknown'])) > 0:
            raise SyncError("git post sync check failed: Working directory is not clean")



    def _git_current_branch(self, host):
        path = self.fullpath(host)
        try:
            raw = host.run_cmd('git symbolic-ref HEAD', tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("git branch detection failed. %s" % str(err))

        m = re.match('^refs/heads/(.*)$', raw)
        if m == None:
            raise SyncError("can't parse output of 'git symbolic-ref HEAD'")

        return m.group(1).strip()



    def _git_ref_exists(self, host, ref):
        path = self.fullpath(host)
        try:
            raw = host.run_cmd('git show-ref --verify -q "%s"' % ref,
                               tgtpath=path, catchout=True)
            return True

        except CmdError:
            return False



    def _git_sync(self, local, remote, silent=False, dryrun=False, batch=False, force=None):
        src = self.fullpath(local)
        tgt = self.fullpath(remote)

        branch = self._git_current_branch(local)
        synced_branch = 'synced/%s' % branch

        args = ['--strategy=recursive']
        if batch: args.append('--ff-only')
        if force == 'up':     args.append('--strategy-option=ours')
        elif force == 'down': args.append('--strategy-option=theirs')

        try:
            # fetch from remote into branch
            if not silent: ui.print_color("fetching from %s" % remote.name)
            if not dryrun: local.run_cmd('git fetch "%s"' % remote.name,
                                         tgtpath=src, silent=silent)

            # if local synced_branch does not exist, create it
            if not self._git_ref_exists(local, 'refs/heads/%s' % synced_branch):
                if not silent: ui.print_color("creating local branch %s" % synced_branch)
                if not dryrun: local.run_cmd('git branch "%s"' % synced_branch,
                                              tgtpath=src, silent=silent)

            # merge synced/branch into branch
            if not silent: ui.print_color("merging local %s into %s" % (synced_branch, branch))
            if not dryrun: local.run_cmd('git merge %s "refs/heads/%s"' % (' '.join(args), synced_branch),
                                         tgtpath=src, silent=silent)

            # merge remote synced/branch into branch
            if self._git_ref_exists(local, 'refs/remotes/%s/%s' % (remote.name, synced_branch)):
                if not silent: ui.print_color("merging remote branch %s into %s" % (synced_branch, branch))
                if not dryrun: local.run_cmd('git merge %s "refs/remotes/%s/%s"' % (' '.join(args),
                                                                                    remote.name, synced_branch),
                                             tgtpath=src, silent=silent)

            # merge remote branch into branch
            if self._git_ref_exists(local, 'refs/remotes/%s/%s' % (remote.name, branch)):
                if not silent: ui.print_color("merging remote branch %s into %s" % (branch, branch))
                if not dryrun: local.run_cmd('git merge %s "refs/remotes/%s/%s"' % (' '.join(args),
                                                                                    remote.name, branch),
                                             tgtpath=src, silent=silent)

            # update synced/branch. We don't want to check it out, as it would be a
            # fast-forward for sure, we just update the branch ref
            if not silent: ui.print_color("updating local branch %s" % synced_branch)
            if not dryrun: local.run_cmd('git branch -f "%s"' % synced_branch,
                                         tgtpath=src, silent=silent)

            # push synced/branch to remote
            if not silent: ui.print_color("pushing branch %s to %s" % (synced_branch, remote.name))
            if not dryrun: local.run_cmd('git push "%s" "refs/heads/%s"' % (remote.name, synced_branch),
                                         tgtpath=src, silent=silent)

            # do a merge on the remote if the branches match
            if self._git_current_branch(remote) == branch:
                if not dryrun: remote.run_cmd('git merge --ff-only "refs/heads/%s"' % synced_branch,
                                              tgtpath=tgt, silent=silent)

        except CmdError as err:
            raise SyncError("git sync failed. %s" % str(err))



    def _parse_git_status(self, host):
        path = self.fullpath(host)
        sta_re = re.compile('^(..)\s*(.*)$', flags=re.MULTILINE)
        try:
            # catch status
            raw = host.run_cmd("git status --porcelain",
                               tgtpath=path, catchout=True)

        except CmdError as err:
            raise SyncError("git status failed. %s" % str(err))

        dic = {}
        dic['staged'] = []
        dic['ignored'] = []
        dic['changed'] = []
        dic['deleted'] = []
        dic['conflicts'] = []
        dic['untracked'] = []
        dic['unknown'] = []

        for st, f in sta_re.findall(raw):
            X, Y = (st[0], st[1])
            if   X in "MADRC"  and Y in " " : dic['staged'].append(f)
            elif X in "MADRC " and Y in "MT": dic['changed'].append(f)
            elif X in "MARC "  and Y in "D":  dic['deleted'].append(f)
            elif X in "U" or Y in "U":        dic['conflicts'].append(f)
            elif X in "A" and Y in "A":       dic['conflicts'].append(f)
            elif X in "D" and Y in "D":       dic['conflicts'].append(f)
            elif X in "?" and Y in "?":       dic['untracked'].append(f)
            elif X in "!" and Y in "!":       dic['ignored'].append(f)
            else:                             dic['unknown'].append(f)

        return dic



    # Interface
    # ----------------------------------------------------------------

    def status(self, host, slow=False):
        status = super(GitDir, self).status(host, slow=slow)
        path = os.path.join(host.path, self.relpath)
        status['type'] = 'git'

        # number of files
        try:
            raw = host.run_cmd("git ls-files | wc -l",
                               tgtpath=path, catchout=True).strip()
            status['numfiles'] = int(raw)
        except:
            status['numfiles'] = -1

        # changed files since last commit
        try:
            raw = host.run_cmd("git status --porcelain" ,tgtpath=path, catchout=True).strip()
            if len(raw) == 0:    status['changed'] = 0
            else:                status['changed'] = len(raw.split('\n'))

        except:
            status['changed'] = -1

        # git status
        st = self._parse_git_status(host)
        status['staged']    = len(st['staged'])
        status['changed']   = len(st['changed']) + len(st['deleted']) + len(st['untracked']) + len(st['unknown'])
        status['conflicts'] = len(st['conflicts'])

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):
        super(GitDir, self).sync(local, remote, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)
        # TODO: implement ignore
        # TODO: implement force to resolve merge conflicts

        if opts:
            batch = opts.batch
            force = opts.force
        else:
            batch = False
            force = None


        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'pre_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)

        # pre sync check
        self._git_pre_sync_check(local, silent=silent, dryrun=dryrun)

        # do the sync
        self._git_sync(local, remote, silent=silent, dryrun=dryrun, batch=batch, force=force)

        # post sync check
        self._git_post_sync_check(local, silent=silent, dryrun=dryrun)

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'post_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # do basic checks
        self.check_paths(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_init', tgt=path, silent=silent, dryrun=dryrun)

        # call init on the parent
        super(GitDir, self).init(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # initialize git
        if not host.path_exists(os.path.join(path, '.git')):
            self._init_git(host, silent=silent, dryrun=dryrun)

        # setup git remotes
        for k, r in self.git_remotes.items():

            # discard remotes named as the host or dead
            if r['name'] == host.name: continue

            if r['dead']:
                self._remove_git_remote(host, r, silent=silent, dryrun=dryrun)

            else:
                self._configure_git_remote(host, r, silent=silent, dryrun=dryrun)

        # symlink git hooks, even if it does not exist
        if len(self.git_hooks_dir) > 0:
            if not silent: ui.print_color("symlinking git hooks")
            host.symlink('../%s' % self.git_hooks_dir, os.path.join(path, '.git/hooks'), force=True)

        # setup git hooks without symlinking
        else:
            remote = self.git_remotes.get(host.name, None)
            if remote and 'git_hooks' in remote and self.name in remote['git_hooks']:
                hooks = remote['git_hooks'][self.name]
                for h, p in hooks.items():
                    self._configure_git_hook(host, h, p, silent=silent, dryrun=dryrun)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # do basic checks
        self.check_paths(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_check', tgt=path, silent=silent, dryrun=dryrun)

        # call check on the parent
        super(GitDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)

        # run git fsck
        try:
            if not silent: ui.print_color("checking git")
            ui.print_debug('git fsck')
            if not dryrun: host.run_cmd("git fsck", tgtpath=path, silent=silent)

        except CmdError as err:
            raise CheckError("git fsck failed. %s" % str(err))

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_check', tgt=path, silent=silent, dryrun=dryrun)
