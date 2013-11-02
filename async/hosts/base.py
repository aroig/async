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
import sys
import subprocess
import time
import shlex
from datetime import datetime

from async.pathdict import PathDict
import async.archui as ui


if sys.version_info[0] < 3:
    def shquote(s):
        return "'" + s.replace("'", "'\"'\"'") + "'"
else:
    shquote = shlex.quote

class HostError(Exception):
    def __init__(self, msg=None):
        super(HostError, self).__init__(msg)


class CmdError(HostError):
    def __init__(self, msg=None, returncode=None, output=""):
        super(CmdError, self).__init__(msg)
        self.output = output
        self.returncode = returncode


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
        self.check_mounts     = conf['check']
        self.mounts           = conf['mounts']
        self.luks_mounts      = conf['luks']
        self.ecryptfs_mounts  = conf['ecryptfs']

        self.annex_pull = set(conf['annex_pull'])
        self.annex_push = set(conf['annex_push'])

        if conf['vol_keys']: self.vol_keys = self.read_keys(conf['vol_keys'])
        else:                self.vol_keys = {}

        # directories
        self.dirs = {}
        for name, dconf in conf['dirs'].items():
            self.dirs[name] = get_directory(dconf, unison_as_rsync=conf['unison_as_rsync'])

        # ignore paths
        self.ignore = conf['ignore']

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


    def _get_common_dirs(self, local, remote, dirs):
        """Returns a dict of dir objects that are common in local and remote as paths.
           Only allows for directories with name in dirs, if dirs != None.
           Avoid subdirectories ignored by one of the hosts."""
        if dirs != None: dirs = set(dirs)
        A = local.dirs
        B = remote.dirs

        igA = PathDict({rel: rel for rel in local.ignore})
        igB = PathDict({rel: rel for rel in remote.ignore})

        # A pathdict has paths as keys. the we can do intersections or unions of the keys
        # and chooses the value for the most specific of the keys.
        pdA = PathDict({d.relpath: d for k, d in A.items()})
        pdB = PathDict({d.relpath: d for k, d in B.items()})
        pdI = pdA & pdB

        return {d.name: d for p, d in pdI.items()
                if (dirs==None or d.name in dirs) and
                not d.relpath in igA and
                not d.relpath in igB}




    # Filesystem manipulations
    # ----------------------------------------------------------------

    def mount_devices(self):
        """Mounts local devices on the host. Takes care of luks and ecryptfs partitions.
           The order is: open luks, mount devices, setup ecryptfs partitions."""
        # open luks partitions
        for dev, name in self.luks_mounts.items():
            passphrase = self.vol_keys[name]
            try:
                self.run_cmd('echo -n %s | sudo cryptsetup --key-file=- open --type luks %s %s' % \
                             (shquote(passphrase), shquote(dev), shquote(name)), tgtpath='/', catchout=True)

            except CmdError as err:
                raise HostError("Can't open luks partition %s. Messge: %s" % (name, err.stdout.strip()))

        # mount devices
        for dev, mp in self.mounts.items():
            try:
                self.run_cmd('sudo mount %s' % shquote(mp), tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't mount %s. Message: %s" % (mp, err.stdout.strip()))

        # mount ecryptfs
        # TODO: needs testing
        for cryp, mp in self.ecryptfs_mounts.items():
            passphrase = self.vol_keys[mp]

            try:
                raw = self.run_cmd('echo -n %s | sudo ecryptfs-add-passphrase -' % shquote(passphrase),
                                   catchout=True)
                sig = re.search("\[(.*?)\]", raw).group(1)
                options = "no_sig_cache,ecryptfs_unlink_sigs,key=passphrase,ecryptfs_cipher=aes," + \
                          "ecryptfs_key_bytes=16,ecryptfs_passthrough=n,ecryptfs_enable_filename_crypto=y," + \
                          "ecryptfs_sig=%s,ecryptfs_fnek_sig=%s" % (sig, sig)

                self.run_cmd('sudo mount -i -t ecryptfs -o %s %s.crypt %s' % (shquote(options),
                                                                              shquote(cryp),
                                                                              shquote(mp)),
                             tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't mount ecryptfs directory %s. Message: %s" % (mp, err.stdout.strip()))


    def umount_devices(self):
        # umount ecryptfs
        for cryp, mp in self.ecryptfs_mounts.items():
            try:
                self.run_cmd('sudo umount %s' % shquote(mp), tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't umount ecryptfs directory %s. Message: %s" % (mp, err.stdout.strip()))

        # umount devices
        for dev, mp in self.mounts.items():
            try:
                self.run_cmd('sudo umount %s' % shquote(mp), tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't umount %s. Message: %s" % (mp, err.stdout.strip()))

        # close luks partitions
        for dev, name in self.luks_mounts.items():
            try:
                self.run_cmd('sudo cryptsetup close --type luks %s' % shquote(name), tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't close luks partition %s. Message: %s" % (name, err.stdout.strip()))


    def check_devices(self):
        """Checks whether all devices are properly mounted, and path checks are ok"""
        # detect if some mountpoint is mising
        for dev, mt in self.mounts.items():
            if not self.check_path_mountpoint(mt):
                ui.print_debug("path %s is not mounted" % mt)
                return False

        # check whether basepath exists
        if not self.path_exists(self.path):
            ui.print_debug("path %s does not exist" % self.path)
            return False

        return True


    def check_paths(self):
        """Checks directories that are required to be present. Returns true if all checks
        pass, or raises an exception with information about what failed."""

        if not check_devices():
            raise HostException("There are unmounted devices")

        for p in self.check_mounts:
            path = os.path.join(self.path, p)
            if not self.path_exists(path):
                ui.print_debug("path %s does nit exist" % path)
                raise HostException("path %s does nit exist" % path)
                return False

        return True


    def check_path_mountpoint(self, path):
        """Returns true if path is a mountpoint"""
        try:
            self.run_cmd('mountpoint -q %s' % shquote(path), tgtpath='/', catchout=True)
            return True
        except CmdError as err:
            return False



    def df(self, path):
        """Run df on the remote and return a tuple of integers (size, available)"""
        try:
            out = self.run_cmd('df %s' % shquote(path), catchout=True)
            device, size, used, available, percent, mountpoint = out.split("\n")[1].split()
            return (int(size), int(available))
        except CmdError as err:
            raise HostError("Can't check disk usage")


    def _print_status(self):
        info = self.get_info()

        ui.print_status("Status of #*m%s#t" % self.name)
        ui.print_color("")

        if 'state' in info: ui.print_color('   #*wstate:#t %s' % info['state'])

        if 'ami_name' in info and 'ami_id' in info:
            ui.print_color('     #*wami:#t %s (%s)' % (info['ami_id'], info['ami_name']))
        if 'instance' in info and 'itype' in info:
            ui.print_color('    #*winst:#t %s (%s)' % (info['instance'], info['itype']))
        if 'block' in info:
            ui.print_color('   #*wblock:#t %s' % ', '.join(
                ['%s (%s)' % (k, s) for k, s in info['block'].items()]))

        if 'host' in info:
            ui.print_color('    #*whost:#t %s' % info['host'])
        if 'ip' in info:
            ui.print_color('      #*wip:#t %s' % info['ip'])

        if 'size' in info:
            ui.print_color('    #*wsize:#t %s' % self.bytes2human(1024*info['size']))
        if 'free' in info:
            ui.print_color('    #*wfree:#t %3.2f%%' % (100 * float(info['free']) / float(info['size'])))

        ui.print_color("")



    # Interface
    # ----------------------------------------------------------------

    def start(self, silent=False, dryrun=False):
        """Starts the host if not running"""
        st = 'online'
        ret = True
        try:
            self.connect(silent=silent, dryrun=False)
        except HostError:
            pass

        try:
            if self.STATES.index(self.state) < self.STATES.index('online'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        finally:
            self.disconnect(silent=silent, dryrun=False)

        return ret


    def stop(self, silent=False, dryrun=False):
        """Stops the host if running"""
        st = 'offline'
        ret = True
        try:
            self.connect(silent=silent, dryrun=False)
            if self.STATES.index(self.state) >= self.STATES.index('online'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        finally:
            self.disconnect(silent=silent, dryrun=False)

        return ret


    def mount(self, silent=False, dryrun=False):
        """Mounts partitions on host, starting it if necessary"""
        st = 'mounted'
        ret = True
        try:
            self.connect(silent=silent, dryrun=False)
            if self.STATES.index(self.state) < self.STATES.index('mounted'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        finally:
            self.disconnect(silent=silent, dryrun=False)

        return ret


    def umount(self, silent=False, dryrun=False):
        """Umounts partitions on host if mounted"""
        st = self.STATES[self.STATES.index('mounted') - 1]
        ret = True
        try:
            self.connect(silent=silent, dryrun=False)
            if self.STATES.index(self.state) >= self.STATES.index('mounted'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        finally:
            self.disconnect(silent=silent, dryrun=False)

        return ret


    def print_status(self, silent=False, dryrun=False):
        try:
            self.connect(silent=silent, dryrun=False)
            self._print_status()

        except HostError as err:
            ui.print_error(str(err))

        finally:
            self.disconnect(silent=silent, dryrun=False)

        return True


    def shell(self, silent=False, dryrun=False):
        """Opens a shell to host"""
        try:
            self.connect()

            # mount remote
            remote_state = self.get_state()
            if not self.set_state('mounted') == 'mounted':
                ui.print_error("Remote host is not in 'mounted' state")
                return False

            ui.print_color("")
            ret = self.interactive_shell()
            if ret != 0:
                ui.print_error("Shell returned with code %d" % ret)
            ui.print_color("")

            # recover old remote state
            self.set_state(remote_state)

        except HostError as err:
            ui.print_error(str(err))

        finally:
            self.disconnect(silent=silent, dryrun=False)


    def run(self, script, silent=False, dryrun=False):
        """Runs a local script on the host"""
        try:
            self.connect()

            # mount remote
            remote_state = self.get_state()
            if not self.set_state('mounted') == 'mounted':
                ui.print_error("Remote host is not in 'mounted' state")
                return False

            ui.print_color("")
            self.run_script(script)

            # recover old remote state
            self.set_state(remote_state)

        except HostError as err:
            ui.print_error(str(err))

        except CmdError as err:
            ui.print_error("Command error on %s: %s" % (self.name, str(err)))

        finally:
            self.disconnect(silent=silent, dryrun=False)


    def backup(self, silent=False, dryrun=False):
        """Creates a data backup"""
        raise NotImplementedError


    def snapshot(self, silent=False, dryrun=False):
        """Creates a server backup"""
        raise NotImplementedError


    def run_on_dirs(self, dirs, func, action, silent=False):
        """Utility function to run a function on a set of directories.
           func(d) operates on a dir object d."""
        from async.directories import InitError, HookError, SyncError, CheckError

        failed = []
        keys = sorted(dirs.keys())
        num = len(keys)
        ret = True

        ui.print_status("%s on #*m%s#*w. %s" % (action, self.name,
                                                datetime.now().strftime("%a %d %b %Y %H:%M")))
        ui.print_color("")

        for i, k in enumerate(keys):
            d = dirs[k]
            if not silent: ui.print_enum(i+1, num, "%s #*y%s#t (%s)" % (action.lower(), d.name, d.type))

            try:
                func(d)

            except (CheckError, InitError, SyncError) as err:
                ui.print_error("%s failed: %s" % (action.lower(), str(err)))
                failed.append(d.name)

            except HookError as err:
                ui.print_error("hook failed: %s" % str(err))
                failed.append(d.name)

            except HostError as err:
                ui.print_error("host error: %s" % str(err))
                failed.append(d.name)

            ret = False

            ui.print_color("")

        if len(failed) == 0:
            ui.print_color("%s #*gsuceeded#t.\n" % action)
            return True

        elif len(failed) > 0:
            ui.print_color("%s #*rfailed#t." % action)
            ui.print_color("  directories: %s" % ', '.join(failed))
            ui.print_color("\n")
            return False



    def sync(self, remote, silent=False, dryrun=False, opts=None):
        raise NotImplementedError



    def init(self, silent=False, dryrun=False, opts=None):
        """Prepares a host for the initial sync. sets up directories, and git annex repos"""
        dirs = self._get_common_dirs(self, self, dirs=opts.dirs)

        try:
            self.connect(silent=silent, dryrun=False)

            def func(d):
                d.init(self, silent=silent or opts.terse, dryrun=dryrun, opts=opts)

            return self.run_on_dirs(dirs, func, "Init", silent=silent)

        except HostError as err:
            ui.print_error("can't connect to host: %s" % str(err))
            return False

        finally:
            self.disconnect(silent=silent, dryrun=False)



    def check(self, silent=False, dryrun=False, opts=None):
        """Check directories for local machine"""
        dirs = self._get_common_dirs(self, self, dirs=opts.dirs)

        try:
            self.connect(silent=silent, dryrun=False)

            def func(d):
                d.check(self, silent=silent or opts.terse, dryrun=dryrun, opts=opts)

            return self.run_on_dirs(dirs, func, "Check", silent=silent)

        except HostError as err:
            ui.print_error("host error: %s" % str(err))
            return False

        finally:
            self.disconnect(silent=silent, dryrun=False)



    # Filesystem manipulations
    # ----------------------------------------------------------------

    def symlink(self, tgt, path):
        try:
            self.run_cmd('ln -s %s %s' % (shquote(tgt), shquote(path)))
        except CmdError as err:
            raise HostError("Can't create symlink on %s" % self.name)


    def path_exists(self, path):
        """Returns true if given path exists"""
        try:
            self.run_cmd('[ -e %s ]' % shquote(path), tgtpath='/')
            return True
        except CmdError as err:
            return False


    def mkdir(self, path, mode):
        try:
            self.run_cmd('mkdir -m %o %s' % (mode, shquote(path)))
        except CmdError as err:
            raise HostError("Can't create directory on %s" % self.name)



    # Implementation
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


    def connect(self, silent=False, dryrun=False):
        """Establishes a connection and initialized data"""
        raise NotImplementedError


    def disconnect(self, silent=False, dryrun=False):
        """Closes a connection and initialized data"""
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


    def get_state(self):
        """Queries the state of the host"""
        raise NotImplementedError


    def get_info(self):
        """Gets a dictionary with host state parameters"""
        raise NotImplementedError


    def run_cmd(self, cm, tgtpath=None, catchout=False, stdin=None):
        """Run a shell command in a given path at host"""
        raise NotImplementedError


    def interactive_shell(self):
        """Opens an interactive shell to host. Returns the shell return code"""
        raise NotImplementedError


    def run_script(self, scrpath, tgtpath=None, catchout=False):
        """Run a script in a local path on the host"""

        with open(scrpath, 'r') as fd:
            script=fd.read()
            ret = self.run_cmd("bash -s", tgtpath=tgtpath, catchout=catchout, stdin=script)

        return ret


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


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
