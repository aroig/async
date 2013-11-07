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
import re
import async.cmd as cmd
import async.archui as ui

class GitDir(BaseDir):
    """Directory synced via git"""

    def __init__(self, conf):
        super(GitDir, self).__init__(conf)
        self.git_remotes = conf['git_remotes']
        self.git_hooks_path = conf['conf_path']



    def _init_git(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        if not silent: ui.print_color("initializing git repo")
        try:
            if not dryrun: host.run_cmd('git init', tgtpath=path)

        except CmdError as err:
            raise InitError("git init failed: %s" % str(err))



    def _configure_git_remote(self, host, rmt, silent=False, dryrun=False):
        path = self.fullpath(host)
        name = rmt['name']
        url = rmt['url'].replace('%d', self.relpath)

        # get currently configured url for the remote
        cur_url = host.run_cmd('git config remote.%s.url' % name,
                               tgtpath=path, catchout=True).strip()

        # add repo if not configured
        if len(cur_url) == 0:
            if not silent: ui.print_color("adding remote '%s'" % name)
            try:
                if not dryrun: host.run_cmd('git remote add "%s" "%s"' % (name, url), tgtpath=path)

            except CmdError as err:
                raise InitError("git remote add failed: %s" % str(err))



    def _configure_git_hook(self, host, hook, hook_path, silent=False, dryrun=False):
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



    def _git_pre_sync_check(self, host, silent=False, dryrun=False):
        path = self.fullpath(host)
        try:
            raw = host.run_cmd("find . -path './.git' -prune -or -print | grep '\.git'",
                               tgtpath=path, catchout=True)
            if len(raw.strip()) > 0:
                ui.print_warning("directory %s on %s contains a nested git repo. It will be ignored." % (self.name, host.name))

        except CmdError as err:
            raise SyncError(str(err))




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

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):
        super(GitDir, self).sync(local, remote, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)
        # TODO: implement ignore
        # TODO: implement force to resolve merge conflicts

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', silent=silent, dryrun=dryrun)
            self.run_hook(local, 'pre_sync_remote', silent=silent, dryrun=dryrun)

        # pre sync check
        self._git_pre_sync_check(local, silent=silent, dryrun=dryrun)

        # TODO: fetch, merge push sequence.

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', silent=silent, dryrun=dryrun)
            self.run_hook(local, 'post_sync_remote', silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

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
            # discard remotes named as the host
            if r['name'] == host.name: continue
            self._configure_git_remote(host, r, silent=silent, dryrun=dryrun)

        # setup git hooks
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

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'check', tgt=path, silent=silent, dryrun=dryrun)

        # call check on the parent
        super(GitDir, self).check(host, silent=silent, dryrun=dryrun, opts=opts, runhooks=False)
