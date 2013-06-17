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


from async.directories import UnisonDir, RsyncDir, AnnexDir, LocalDir
import async.archui as ui

class HostError(Exception):
    def __init__(self, msg=None):
        super(self, HostError).__init__(msg)



class BaseHost(object):
    STATES = ['offline', 'online', 'mounted']

    def __init__(self, conf):
        super(BaseHost, self).__init__()

        self.type = None
        self.state = None

        # name and path
        self.name = conf['name']
        self.path = conf['path']

        self.mounts = conf['mounts']
        self.luks = conf['luks']
        self.luks_key = self.read_luks_keys(conf['luks_key'])

        # directories
        self.dirs = {}
        for k, d in conf['dirs'].items():
            self.dirs[k] = self.get_directory(d, unison_as_rsync=conf['unison_as_rsync'])


    def get_directory(self, dconf, unison_as_rsync=False):
        typ = dconf['type']
        if unison_as_rsync and typ == 'unison': typ = 'rsync'

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


    def switch_state(self, msg, tgtstate, silent=False, dryrun=False):
        """Switches host state to tgtstate"""
        try:
            if not silent: ui.print_status(text=msg, flag="BUSY")
            if not dryrun: self.set_state(tgtstate)
            if not silent: ui.print_status(flag="DONE", nl=True)

        except HostError:
            if not silent: ui.print_status(flag="FAIL", nl=True)


    def bytes2human(self, n, format="%(value)3.2f %(symbol)s"):
        """
        >>> bytes2human(10000)
        '9 Kb'
        >>> bytes2human(100001221)
        '95 Mb'
        """
        symbols = ('b', 'Kb', 'Mb', 'Gb', 'Tb', 'Pb', 'Eb', 'Zb', 'Yb')
        prefix = {}
        for i, s in enumerate(symbols[1:]):
            prefix[s] = 1 << (i+1)*10
        for symbol in reversed(symbols[1:]):
            if n >= prefix[symbol]:
                value = float(n) / prefix[symbol]
                return format % locals()
        return format % dict(symbol=symbols[0], value=n)


    def read_luks_keys(self, path):
        """Reads luks keys from a file. each line is formatted as id:key"""
        keys = {}
        with open(path, 'r') as fd:
            for line in fd:
                m = re.match(r'^(.*):(.*)$')
                if m: keys[m.group(1).strip()] = m.group(2).strip()

        return keys


    # Commands
    # ----------------------------------------------------------------

    def mount_devices(self):
        # open luks partitions
        for dev, name in self.luks.items():
            passphrase = self.luks_key[name]

            try:
                self.run_cmd('sudo sh -c "echo -n %s | cryptsetup --key-file=- luksOpen %s %s"' % \
                             (passphrase, dev, name))

            except subprocess.CalledProcessError:
                ui.print_error("Can't open luks partition %s" % name)

        # mount devices
        for dev, mp in self.mounts.items():
            try:
                self.run_cmd('mount "%s"' % mp, tgtpath='/')
            except subprocess.CalledProcessError:
                ui.print_error("Can't mount %s" % mp)


    def umount_devices(self):
        # umount devices
        for dev, mp in self.mounts.items():
            try:
                self.run_cmd('umount "%s"' % mp, tgtpath='/')

            except subprocess.CalledProcessError:
                ui.print_error("Can't umount %s" % mp)

        # close luks partitions
        for dev, name in self.luks.items():
            try:
                self.run_cmd('sudo cryptsetup luksClose %s' % name)

            except subprocess.CalledProcessError:
                ui.print_error("Can't close luks partition %s" % name)



    def df(self, path):
        """Run df on the remote and return a tuple of integers (size, available)"""
        out = self.run_cmd('df "%s"' % path, catchout=True)
        device, size, used, available, percent, mountpoint = out.split("\n")[1].split()
        return (int(size), int(available))


    # Interface
    # ----------------------------------------------------------------

    def type(self):
        """Returns the type of host"""
        return self.type


    def start(self, silent=False, dryrun=False):
        """Starts the host"""
        if self.get_state() in set(['offline']):
            self.switch_state("Starting %s" % (self.name), 'online', silent=silent, dryrun=dryrun)


    def stop(self, silent=False, dryrun=False):
        """Stops the host"""
        if not self.get_state() in set(['offline']):
            self.switch_state("Stopping %s" % (self.name), 'offline', silent=silent, dryrun=dryrun)


    def mount(self, silent=False, dryrun=False):
        """Mounts the partitions on host"""
        if not self.get_state() in set(['mounted']):
            self.switch_state("Mounting devices for %s" % (self.name), 'mounted', silent=silent, dryrun=dryrun)


    def umount(self, silent=False, dryrun=False):
        """Umounts the partitions on host"""
        if self.get_state() in set(['mounted']):
            self.switch_state("Umounting devices for %s" % (self.name), 'online', silent=silent, dryrun=dryrun)


    def print_status(self):
        info = self.get_info()

        ui.print_status("Status of #m%s#t" % self.name)

        if 'state' in info: ui.print_color('   #*wstate:#t %s' % info['state'])
        if 'size' in info:  ui.print_color('    #*wsize:#t %s' % self.bytes2human(1024*info['size']))
        if 'free' in info:  ui.print_color('    #*wfree:#t %3.2f%%' % (100 * float(info['free']) / float(info['size'])))


    def shell(self):
        """Opens a shell to host"""
        if not self.get_state() in set(['mounted']):
            ui.print_error("Not mounted")
            return

        self.interactive_shell()



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

    def run_cmd(self, c, tgtpath=None, catchout=False):
        """Run a shell command in a given path at host"""
        raise NotImplementedError

    def run_script(self, scr_path):
        """Run script on a local path on the host"""
        raise NotImplementedError

    def interactive_shell(self):
        """Opens an interactive shell to host"""
        raise NotImplementedError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
