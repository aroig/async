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


from async.directories import UnisonDir, AnnexDir, LocalDir


class HostError(Exception):
    def __init__(self, msg=None):
        super(self, HostError).__init__(msg)



class BaseHost(object):
    STATES = ['offline', 'online', 'mounted']

    def __init__(self, conf):
        self.type = None
        self.state = None

        # name and path
        self.name = conf['name']
        self.path = conf['path']

        # directories
        self.dirs = {}
        for k, d in conf['dirs'].items():
            self.dirs[k] = self.get_directory(d)


    def get_directory(self, dconf):
        typ = dconf['type']
        if typ == 'unison':   return UnisonDir(basepath=self.path, conf=dconf)
        elif typ == 'rsync':  return RsyncDir(basepath=self.path, conf=dconf)
        elif typ == 'annex':  return AnnexDir(basepath=self.path, conf=dconf)
        elif typ == 'local':  return LocalDir(basepath=self.path, conf=dconf)
        else:
            raise HostError("Unknown directory type %s" % typ)



    # Utilities
    # ----------------------------------------------------------------

    def wait_for(self, status, func, timeout=120):
        """Waits until func returns status. A timeout in seconds can be specified"""
        time_passed = 0
        step = 2
        while func() != status and time_passed <= timeout:
            time.sleep(step)
            time_passed = time_passed + step

        return func() == status



    # Interface
    # ----------------------------------------------------------------

    def type(self):
        """Returns the type of host"""
        return self.type


    def start(self, opts):
        """Starts the host"""
        if self.get_state() in set(['offline']):
            self.set_state('online')


    def stop(self, opts):
        """Stops the host"""
        if not self.get_state() in set(['offline']):
            self.set_state('offline')


    def mount(self, opts):
        """Mounts the partitions on host"""
        if not self.get_state() in set(['mounted']):
            self.set_state('mounted')


    def umount(self, opts):
        """Umounts the partitions on host"""
        if self.get_state() in set(['mounted']):
            self.set_state('online')


    def print_status(self, opts):
        status = self.get_info()

        ui.print_status("Status of #m%s#t" % self.name)

        for k, val in status.items():
            ui.print_color('#*w%s:#t %s' % (k, val))


    def shell(self, opts):
        """Opens a shell to host"""
        self.interactive_shell(opts)



    # Abstract methods
    # ----------------------------------------------------------------

    def get_state(self):
        """Queries the state of the host"""
        raise NotImplementedError

    def set_state(self, state):
        """Sets the state of the host"""
        raise NotImplementedError

    def get_info(self):
        """Gets a dictionary with host state parameters"""
        raise NotImplementedError

    def sync_dir(self, conf, opts):
        """Synchronize a local directory with host"""
        raise NotImplementedError

    def run_cmd(self, path, cmd):
        """Run a shell command in a given path at host"""
        raise NotImplementedError

    def run_script(self, scrpath, path):
        """Run script on a local path on the host"""
        raise NotImplementedError

    def interactive_shell(self, opts):
        """Opens an interactive shell to host"""
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
