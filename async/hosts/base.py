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

import re
import subprocess
import time

import async.archui as ui

class HostError(Exception):
    def __init__(self, msg=None):
        super(HostError, self).__init__(msg)



class BaseHost(object):
    STATES = ['offline', 'online', 'mounted']

    def __init__(self, conf):
        from async.directories import get_directory

        super(BaseHost, self).__init__()

        self.state = None

        # name and path
        self.name = conf['name']
        self.path = conf['path']

        # mounts
        self.check = conf['check']
        self.mounts = conf['mounts']
        self.luks = conf['luks']
        self.ecryptfs = conf['ecryptfs']

        if conf['vol_keys']: self.vol_keys = self.read_keys(conf['vol_keys'])
        else:                self.vol_keys = {}

        # directories
        self.dirs = {}
        for k, d in conf['dirs'].items():
            self.dirs[k] = get_directory(self.path, d, unison_as_rsync=conf['unison_as_rsync'])


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


    def read_keys(self, path):
        """Reads keys from a file. each line is formatted as id = key"""
        keys = {}
        with open(path, 'r') as fd:
            for line in fd:
                m = re.match(r'^(.*)=(.*)$', line)
                if m: keys[m.group(1).strip()] = m.group(2).strip()

        return keys


    # Filesystem manipulations
    # ----------------------------------------------------------------

    def mount_devices(self):
        """Mounts local devices on the host. Takes care of luks and ecryptfs partitions.
           The order is: open luks, mount devices, setup ecryptfs partitions."""
        # open luks partitions
        for dev, name in self.luks.items():
            passphrase = self.vol_keys[name]
            ret = self.run_cmd('sudo sh -c "echo -n %s | cryptsetup --key-file=- luksOpen %s %s"; echo $?' % \
                               (passphrase, dev, name),
                               tgtpath='/', catchout=True)
            if ret.strip() != '0':
                raise HostError("Can't open luks partition %s" % name)

        # mount devices
        for dev, mp in self.mounts.items():
            ret = self.run_cmd('mount "%s"; echo $?' % mp,
                               tgtpath='/', catchout=True)
            if ret.strip() != '0':
                raise HostError("Can't mount %s" % mp)

        # mount ecryptfs
        # TODO: needs testing
        for cryp, mp in self.ecryptfs.items():
            passphrase = self.vol_keys[mp]

            raw = self.run_cmd('sudo sh -c "echo -n %s | ecryptfs-add-passphrase -"', catchout=True)
            sig = re.search("\[(.*?)\]", raw).group(1)
            options = "no_sig_cache,ecryptfs_unlink_sigs,key=passphrase,ecryptfs_cipher=aes," + \
                      "ecryptfs_key_bytes=16,ecryptfs_passthrough=n,ecryptfs_enable_filename_crypto=y," + \
                      "ecryptfs_sig=%s,ecryptfs_fnek_sig=%s" % (sig, sig)

            ret = self.run_cmd('sudo mount -i -t ecryptfs -o %s %s.crypt "%s"; echo $?' % (options, cryp, mp),
                               tgtpath='/', catchout=True)
            if ret.strip() != '0':
                raise HostError("Can't mount ecryptfs directory %s" % mp)


    def umount_devices(self):
        # umount ecryptfs
        for cryp, mp in self.ecryptfs.items():
            ret = self.run_cmd('umount "%s"; echo $?' % mp,
                               tgtpath='/', catchout=True)
            if ret.strip() != '0':
                raise HostError("Can't umount ecryptfs directory %s" % mp)

        # umount devices
        for dev, mp in self.mounts.items():
            ret = self.run_cmd('umount "%s"; echo $?' % mp,
                               tgtpath='/', catchout=True)
            if ret.strip() != '0':
                raise HostError("Can't umount %s" % mp)

        # close luks partitions
        for dev, name in self.luks.items():
            ret = self.run_cmd('sudo cryptsetup luksClose %s; echo $?' % name,
                               tgtpath='/', catchout=True)
            if ret.strip() != '0':
                raise HostError("Can't close luks partition %s" % name)


    def check_devices(self):
        """Checks whether all devices are properly mounted, and path checks are ok"""
        # detect if some mountpoint is mising
        for dev, mt in self.mounts.items():
            if not self.check_path_mountpoint(mt):
                ui.print_debug("path %s is not mounted" % mt)
                return False

        # check whether basepath exists
        if not self.check_path_exists(self.path):
            ui.print_debug("path %s does not exist" % self.path)
            return False

        return True


    def check_paths(self):
        """Checks directories that are required to be present. Returns true if all checks
        pass, or raises an exception with information about what failed."""

        if not check_devices():
            raise HostException("There are unmounted devices")

        for p in self.check:
            path = os.path.join(self.path, p)
            if not self.path_exists(path):
                ui.print_debug("path %s does nit exist" % path)
                raise HostException("path %s does nit exist" % path)
                return False

        return True


    def check_path_mountpoint(self, path):
        """Returns true if path is a mountpoint"""
        ret = self.run_cmd('mountpoint -q "%s"; echo $?' % path,
                           tgtpath='/', catchout=True)
        return ret.strip() == '0'


    def check_path_exists(self, path):
        """Returns true if given path exists"""
        ret = self.run_cmd('[ -e "%s" ]; echo $?' % path,
                           tgtpath='/',  catchout=True)
        return ret.strip() == '0'


    def df(self, path):
        """Run df on the remote and return a tuple of integers (size, available)"""
        out = self.run_cmd('df "%s"' % path, catchout=True)
        device, size, used, available, percent, mountpoint = out.split("\n")[1].split()
        return (int(size), int(available))



    # Interface
    # ----------------------------------------------------------------

    @property
    def type(self):
        """Returns the type of host as a string"""
        from async.hosts import DirectoryHost, Ec2Host, SshHost, LocalHost
        if isinstance(self, DirectoryHost): return "directory"
        elif isinstance(self, Ec2Host):     return "ec2"
        elif isinstance(self, SshHost):     return "ssh"
        elif isinstance(self, LocalHost):   return "local"
        else:
            raise DirError("Unknown host class %s" % str(type(self)))


    def start(self, silent=False, dryrun=False):
        """Starts the host if not running"""
        st = 'online'
        if self.STATES.index(self.state) < self.STATES.index('online'):
            return self.set_state(st, silent=silent, dryrun=dryrun) == st


    def stop(self, silent=False, dryrun=False):
        """Stops the host if running"""
        st = 'offline'
        if self.STATES.index(self.state) >= self.STATES.index('online'):
            return self.set_state(st, silent=silent, dryrun=dryrun) == st


    def mount(self, silent=False, dryrun=False):
        """Mounts partitions on host, starting it if necessary"""
        st = 'mounted'
        if self.STATES.index(self.state) < self.STATES.index('mounted'):
            return self.set_state(st, silent=silent, dryrun=dryrun) == st


    def umount(self, silent=False, dryrun=False):
        """Umounts partitions on host if mounted"""
        st = self.STATES[self.STATES.index('mounted') - 1]
        if self.STATES.index(self.state) >= self.STATES.index('mounted'):
            return self.set_state(st, silent=silent, dryrun=dryrun) == st


    def print_status(self):
        info = self.get_info()

        ui.print_status("Status of #*m%s#t" % self.name)
        ui.print_color("")

        if 'state' in info: ui.print_color('   #*wstate:#t %s' % info['state'])

        if 'ami_name' in info and 'ami_id' in info:
            ui.print_color('     #*wami:#t %s (%s)' % (info['ami_id'], info['ami_name']))
        if 'instance' in info and 'itype' in info:
            ui.print_color('    #*winst:#t %s (%s)' % (info['instance'], info['itype']))
        if 'block' in info:
            ui.print_color('   #*wblock:#t %s' % ', '.join(['%s (%s)' % (k, s) for k, s in info['block'].items()]))

        if 'host' in info:  ui.print_color('    #*whost:#t %s' % info['host'])
        if 'ip' in info:    ui.print_color('      #*wip:#t %s' % info['ip'])

        if 'size' in info:  ui.print_color('    #*wsize:#t %s' % self.bytes2human(1024*info['size']))
        if 'free' in info:  ui.print_color('    #*wfree:#t %3.2f%%' % (100 * float(info['free']) / float(info['size'])))
        ui.print_color("")


    def shell(self):
        """Opens a shell to host"""
        if not self.get_state() in set(['mounted']):
            ui.print_error("Not mounted")
            return

        self.interactive_shell()


    def connect(self):
        """Establishes a connection and initialized data"""
        raise NotImplementedError


    def backup(self, silent=False, dryrun=False):
        """Creates a data backup"""
        raise NotImplementedError


    def set_state(self, state, silent=False, dryrun=False):
        """Sets the host to the given state, passing through all the states in between."""
        self.state = self.get_state()

        try:
            if not state in self.STATES:
                raise HostError("Unknown state %s" % state)

            cur = self.STATES.index(self.state)
            new = self.STATES.index(state)

            if cur < new:
                for i in range(cur, new, 1):
                    st = self.STATES[i+1]
                    def func():
                        self.enter_state(st)

                    self.run_with_message(func=func,
                                          msg="Entering state %s" % st,
                                          silent=silent,
                                          dryrun=dryrun)
                    self.state = st

            elif cur > new:
                for i in range(cur, new, -1):
                    st = self.STATES[i]
                    def func():
                        self.leave_state(st)

                    self.run_with_message(func=func,
                                          msg="Leaving state %s" % st,
                                          silent=silent,
                                          dryrun=dryrun)
                    self.state = st

        except HostError as err:
            ui.print_error(str(err))
            return self.state

        self.state = self.get_state()
        return self.state


    # State transitions
    # ----------------------------------------------------------------

    def run_with_message(self, func, msg, silent=False, dryrun=False):
        try:
            if not silent: ui.print_status(text=msg, flag="BUSY")
            if not dryrun: func()
            if not silent: ui.print_status(flag="DONE", nl=True)

        except HostError as err:
            if not silent:
                ui.print_status(flag="FAIL", nl=True)
                raise

    def enter_state(self, state):
        raise NotImplementedError

    def leave_state(self, state):
        raise NotImplementedError



    # Abstract methods
    # ----------------------------------------------------------------

    def get_state(self):
        """Queries the state of the host"""
        raise NotImplementedError

    def get_info(self):
        """Gets a dictionary with host state parameters"""
        raise NotImplementedError

    def run_cmd(self, c, tgtpath=None, catchout=False):
        """Run a shell command in a given path at host"""
        raise NotImplementedError

    def interactive_shell(self):
        """Opens an interactive shell to host"""
        raise NotImplementedError

    # TODO: I should be able to implement this with run_cmd
    def run_script(self, scr_path):
        """Run script on a local path on the host"""
        raise NotImplementedError


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
