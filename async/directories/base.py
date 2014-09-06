#!/usr/bin/env on2
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
import re
import subprocess
import json

from datetime import datetime, timedelta

import async.archui as ui
from async.utils import shquote



class DirError(Exception):
    def __init__(self, msg=None):
        super(DirError, self).__init__(msg)

class CheckError(Exception):
    def __init__(self, msg=None):
        super(CheckError, self).__init__(msg)

class SyncError(Exception):
    def __init__(self, msg=None):
        super(SyncError, self).__init__(msg)

class InitError(Exception):
    def __init__(self, msg=None):
        super(InitError, self).__init__(msg)

class HookError(Exception):
    def __init__(self, msg=None):
        super(HookError, self).__init__(msg)

class SkipError(Exception):
    def __init__(self, msg=None):
        super(SkipError, self).__init__(msg)



class BaseDir(object):

    def __init__(self, conf):
        self.name = conf['name']
        self.relpath = conf['path']

        self.perms      = int(conf['perms'], base=8)
        self.symlink    = conf['symlink']
        self.subdirs    = conf['subdirs']

        self.path_rename = conf['path_rename']
        self.lastsync    = conf['save_lastsync']
        self.asynclast_file = conf['asynclast_file']

        self.check_paths_list = conf['check_paths']

        self.hooks = {}
        self.hooks_path = conf['conf_path']

        self.hooks['pre_check']        = conf['pre_check_hook']
        self.hooks['post_check']       = conf['post_check_hook']
        self.hooks['pre_init']         = conf['pre_init_hook']
        self.hooks['post_init']        = conf['post_init_hook']
        self.hooks['pre_sync']         = conf['pre_sync_hook']
        self.hooks['post_sync']        = conf['post_sync_hook']
        self.hooks['pre_sync_remote']  = conf['pre_sync_remote_hook']
        self.hooks['post_sync_remote'] = conf['post_sync_remote_hook']

        self.ignore = list(conf['ignore'])
        self.ignore.append(os.path.join(self.relpath, self.asynclast_file))



    def _create_directory(self, host, path, mode, silent=False, dryrun=False):
        """Creates a directory or symlink. Returns false if it already existed"""

        # if symlink, (re)create it
        if self.symlink:
            tgtlink = os.path.join(host.path, self.symlink)

            if not silent:
                ui.print_color("symlink: %s -> %s" % (path, tgtlink))

            try:
                if not dryrun: host.symlink(tgtlink, path, force=True)

            except Exception as err:
                raise InitError(str(err))

            return True

        # if nonexistent directory, create it
        elif not self.symlink and not host.path_exists(path):
            if not silent:
                ui.print_color("mkdir: %s" % path)

            try:
                if not dryrun: host.mkdir(path, mode=mode)
            except Exception as err:
                raise InitError(str(err))
            return True

        # if directory exists, set perms
        elif not self.symlink and host.path_exists(path):
            if not silent:
                ui.print_color("chmod %o: %s" % (mode, path))

            try:
                if not dryrun: host.chmod(path, mode)
            except Exception as err:
                raise InitError(str(err))

            return True

        # if existent directory that should be a symlinks, do nothing
        else:
            return False



    # Utilities
    # ----------------------------------------------------------------

    @property
    def type(self):
        """Returns the type of the directory as a string"""
        from async.directories import AnnexDir, UnisonDir, RsyncDir, LocalDir, GitDir
        if isinstance(self, AnnexDir):    return 'annex'
        if isinstance(self, GitDir):      return 'git'
        elif isinstance(self, UnisonDir): return 'unison'
        elif isinstance(self, RsyncDir):  return 'rsync'
        elif isinstance(self, LocalDir):  return 'local'
        else:
            raise DirError("unknown directory class %s" % str(type(self)))


    def fullpath(self, host):
        return self.hostpath(host.name, host.path)


    def hostpath(self, hostname, path):
        if hostname in self.path_rename:
            rpath = self.path_rename[hostname]
        else:
            rpath = self.relpath

        return os.path.join(path, rpath)


    def run_hook(self, host, name, tgt=None, silent=False, dryrun=False):
        """Runs hooks"""
        if name in self.hooks:
            for hook in self.hooks[name]:
                if not silent: ui.print_color("running %s hook: %s" % (name, hook))
                hookpath = os.path.join(self.hooks_path, hook)
                if not dryrun:
                    from async.hosts import CmdError
                    try:
                        ret = host.run_script(hookpath, tgtpath=tgt, catchout=True)
                        if not silent: ui.write_color(ret)

                    except CmdError as err:
                        raise HookError("error running hook %s. %s" % (name, str(err)))


    def check_paths(self, host):
        """Checks directories that are required to be present. Returns true if all checks
        pass, or raises an exception with information about what failed."""

        for p in [self.fullpath(host)] + self.check_paths_list:
            path = os.path.join(host.path, p)
            if not host.path_exists(path):
                raise DirError("path %s does not exist on '%s'" % (path, host.name))

        return True



    # Interface
    # ----------------------------------------------------------------

    def is_initialized(self, host):
        return True


    def status(self, host, slow=False):
        """Returns a dict of the status of the directory on host"""
        path = os.path.join(host.path, self.relpath)
        status = {
            'name'     : self.name,
            'relpath'  : self.relpath,
            'path'     : path,
            'type'     : 'base',
        }
        lastsync = host.read_lastsync(self.fullpath(host))
        status['ls-timestamp'] = lastsync['timestamp']
        status['ls-remote'] = lastsync['remote']
        status['ls-success'] = lastsync['success']

        try:
            raw  = host.run_cmd('stat -L -c "%%a %%U:%%G" "%s"' % path, catchout=True)
            m = re.match('^(\d+) ([a-zA-Z]+):([a-zA-Z]+)$', raw)
            status['perms'] = m.group(1)
            status['user']  = m.group(2)
            status['group'] = m.group(3)

        except:
            status['path'] = None
            status['perms'] = '???'
            status['user']  = 'unknown'
            status['group'] = 'unknown'

# NOTE: this is awfully slow
#        size   = 0
#        raw    = host.run_cmd('du -s "%s"' % path, catchout=True)
#        if raw:
#            m = re.match('^(\d+).*$', raw)
#            if m: size = int(m.group(1))

        return status



    def sync(self, local, remote, silent=False, dryrun=False, opts=None, runhooks=True):

        # pre-sync hook
        if runhooks:
            self.run_hook(local, 'pre_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'pre_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)

        # This does nothing, only runs the hooks

        # post-sync hook
        if runhooks:
            self.run_hook(local, 'post_sync', tgt=self.fullpath(local), silent=silent, dryrun=dryrun)
            self.run_hook(remote, 'post_sync_remote', tgt=self.fullpath(remote), silent=silent, dryrun=dryrun)



    def init(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'pre_init', tgt=path, silent=silent, dryrun=dryrun)

        if host.path_exists(path):
            ui.print_warning("path already exists: %s" % path)

        self._create_directory(host, path, self.perms, silent, dryrun)

        # create subdirs
        perms = 0o755
        for sd in self.subdirs:
            sdpath = os.path.join(path, sd)
            self._create_directory(host, sdpath, perms, silent, dryrun)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'post_init', tgt=path, silent=silent, dryrun=dryrun)



    def check(self, host, silent=False, dryrun=False, opts=None, runhooks=True):
        path = self.fullpath(host)

        # run async hooks if asked to
        if runhooks:
            self.run_hook(host, 'check', tgt=path, silent=silent, dryrun=dryrun)

        if not os.path.exists(path):
            raise CheckError("path does not exist: %s" % path)



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
