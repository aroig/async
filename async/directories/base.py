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

class DirError(Exception):
    def __init__(self, msg=None):
        super(DirError, self).__init__(msg)

class SyncError(Exception):
    def __init__(self, msg=None):
        super(SyncError, self).__init__(msg)

class SetupError(Exception):
    def __init__(self, msg=None):
        super(SetupError, self).__init__(msg)


class BaseDir(object):

    def __init__(self, basepath, conf):
        self.name = conf['name']
        self.relpath = conf['path']
        self.path = os.path.join(basepath, conf['path'])


    # Interface
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


    def sync(self, local, remote, silent=False, dryrun=False, opts=None):
        raise NotImplementedError


    def setup(self, host, silent=False, dryrun=False, opts=None):
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
