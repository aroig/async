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

import os
import subprocess

import async.archui as ui

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


class BaseDir(object):

    def __init__(self, conf):
        self.name = conf['name']
        self.relpath = conf['path']

        self.perms      = int(conf['perms'], base=8)
        self.symlink    = conf['symlink']
        self.ignore     = []

        self.path_rename = conf['path_rename']

        self.hooks = {}
        self.hooks_path = conf['conf_path']

        self.hooks['init']             = conf['init_hook']
        self.hooks['pre_sync']         = conf['pre_sync_hook']
        self.hooks['post_sync']        = conf['post_sync_hook']
        self.hooks['pre_sync_remote']  = conf['pre_sync_remote_hook']
        self.hooks['post_sync_remote'] = conf['post_sync_remote_hook']


    def _create_directory(self, host, path, mode, silent=False, dryrun=False):
        """Creates a directory or symlink. Returns false if it already existed"""
        if host.path_exists(path):
            return False

        elif self.symlink:
            if not silent:
                ui.print_color("symlink: %s -> %s" % (path, self.symlink))

            try:
                if not dryrun: host.symlink(self.symlink, path)
            except Exception as err:
                raise InitError(str(err))
            return True

        else:
            if not silent:
                ui.print_color("mkdir: %s" % path)

            try:
                if not dryrun: host.mkdir(path, mode=mode)
            except Exception as err:
                raise InitError(str(err))
            return True


    # Utilities
    # ----------------------------------------------------------------

    @property
    def type(self):
        """Returns the type of the directory as a string"""
        from async.directories import AnnexDir, UnisonDir, RsyncDir, LocalDir
        if isinstance(self, AnnexDir):    return 'annex'
        elif isinstance(self, UnisonDir): return 'unison'
        elif isinstance(self, RsyncDir):  return 'rsync'
        elif isinstance(self, LocalDir):  return 'local'
        else:
            raise DirError("Unknown directory class %s" % str(type(self)))


    def fullpath(self, host):
        if host.name in self.path_rename:
            rpath = self.path_rename[host.name]
        else:
            rpath = self.relpath

        return os.path.join(host.path, rpath)


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
                        ui.print_color(ret)

                    except CmdError as err:
                        raise HookError("error running hook %s: %s" % (name, str(err)))



    # Interface
    # ----------------------------------------------------------------

    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        return



    def init(self, host, silent=False, dryrun=False, opts=None):
        path = self.fullpath(host)

        if not host.path_exists(path):
            if not silent:
                ui.print_color("Creating %s with permissions %o" % (path, self.perms))
            self._create_directory(host, path, self.perms, silent, dryrun)
        else:
            ui.print_warning("path already exists: %s" % path)



    def check(self, host, silent=False, dryrun=False, opts=None):
        path = self.fullpath(host)

        if not os.path.exists(path):
            raise CheckError("path does not exist: %s" % path)




# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
