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
import re
import sys
import json
import subprocess
import systemd.daemon
import time
from datetime import datetime, timedelta
import dateutil.parser
from collections import OrderedDict

from async.pathdict import PathDict
from async.utils import number2human, read_keys, shquote

import async.archui as ui
import async.cmd as cmd


class HostError(Exception):
    def __init__(self, msg=None):
        super(HostError, self).__init__(msg)


class CmdError(HostError):
    def __init__(self, msg=None, cm=None, returncode=None, output=None):
        super(CmdError, self).__init__(msg)
        self.output = output
        self.cmd = cm
        self.returncode = returncode

    def __str__(self):
        errmsg = super(CmdError, self).__str__()
        if self.cmd:    errmsg = errmsg + '\n  cmd: %s' % self.cmd
        if self.output: errmsg = errmsg + '\n  out: %s' % self.output
        return errmsg


class HostController:
    """ Object to handle with statement on hosts"""
    def __init__(self, host, tgtstate=None, silent=False, dryrun=False):
        self.host = host
        self.tgtstate = tgtstate
        self.curstate = None
        self.silent = silent
        self.dryrun = dryrun

    def __enter__(self):
        self.curstate = self.host.get_state()

        if self.tgtstate:
            # change state
            newstate = self.host.set_state(self.tgtstate)
            if not newstate == self.tgtstate:
                raise HostError("Could not bring '%s' host to '%s' state" % (self.host.name, self.tgtstate))

        # notify systemd, in case this is part of a systemd service
        systemd.daemon.notify('\n'.join(['READY=1',
                                         'STATUS="Host %s is mounted"' % self.host.name]))

        return self.host

    def __exit__(self, type, value, traceback):
        # do not get to current state if target state was not specified
        if self.curstate and self.tgtstate:
            self.host.set_state(self.curstate)



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
        self.check_mounts_list = conf['check_mounts']
        self.mounts           = conf['mounts']
        self.luks_mounts      = conf['luks']
        self.ecryptfs_mounts  = conf['ecryptfs']
        self.swapfile         = conf['swapfile']
        self.systemd_user     = conf['kill_systemd_user']
        self.default_remote   = conf['default_remote']
        self.mount_options    = conf['mount_options']

        self.annex_pull       = set(conf['annex_pull'])
        self.annex_push       = set(conf['annex_push'])

        self.log_cmd          = conf['log_cmd']
        self.update_cmd       = conf['update_cmd']

        self.lastsync         = conf['save_lastsync']
        self.asynclast_file   = conf['asynclast_file']

        if conf['vol_keys']: self.vol_keys = read_keys(conf['vol_keys'])
        else:                self.vol_keys = {}

        # directories
        self.dirs = OrderedDict()
        for name, dconf in conf['dirs'].items():
            self.dirs[name] = get_directory(dconf, unison_as_rsync=conf['unison_as_rsync'])

        # ignore paths
        self.ignore = conf['ignore']
        self.ignore.append(self.asynclast_file)



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



    def _get_common_dirs(self, local, remote, dirs, ignore=[]):
        """Returns a dict of dir objects that are common in local and remote as paths.
           Only allows for directories with name in dirs, if dirs != None.
           Avoid subdirectories ignored by one of the hosts."""

        # dicts of local and remote dirs
        A = local.dirs
        B = remote.dirs

        # A pathdict has paths as keys. the we can do intersections or unions of the keys
        # and chooses the value for the most specific of the keys.
        pdA = PathDict([(d.relpath, d) for k, d in A.items()])
        pdB = PathDict([(d.relpath, d) for k, d in B.items()])
        pdI = pdA & pdB
        dd = OrderedDict([(d.name, d) for p, d in pdI.items()])

        # get ignored paths
        igA = PathDict({rel: rel for rel in local.ignore})
        igB = PathDict({rel: rel for rel in remote.ignore})
        igC = PathDict({rel: rel for rel in ignore})

        # remove ignores
        dd = OrderedDict([(k, d) for k, d in dd.items() if not d.relpath in igA
                                                           and not d.relpath in igB
                                                           and not d.relpath in igC])

        # get list of dir names. Order matters.
        if dirs != None: dirs = list(dirs)
        else:            dirs = list(dd.keys())

        # warn about unrecognized directories
        for k in dirs:
            if not k in dd:
                ui.print_warning("Unrecognized directory %s" % k)

        return OrderedDict([(k, dd[k]) for k in dirs if k in dd])




    # Filesystem manipulations
    # ----------------------------------------------------------------

    # NOTE: for running commands I do
    #  ! check || cmd
    # that produces the following truth table of exit status
    #    check   cmd   output
    #      F      X      T
    #      T      T      T
    #      T      F      F


    def mount_devices(self):
        """Mounts local devices on the host. Takes care of luks and ecryptfs partitions.
           The order is: open luks, mount devices, setup ecryptfs partitions."""
        # open luks partitions
        for dev, name in self.luks_mounts.items():
            ui.print_debug("mounting luks: %s %s" % (dev, name))
            passphrase = self.vol_keys[name]
            try:
                self.run_cmd('! (sudo cryptsetup status %s | grep -qs inactive) || ' % shquote(name) +
                             'sudo cryptsetup --key-file=- open --type luks %s %s' % \
                             (shquote(dev), shquote(name)), tgtpath='/', catchout=True, stdin=passphrase)

            except CmdError as err:
                raise HostError("Can't open luks partition. %s" % str(err))

        # mount devices
        for dev, mp in self.mounts.items():
            ui.print_debug("mounting device: %s %s" % (dev, mp))
            try:
                if self.mount_options:
                    mount_cmd = 'sudo mount -o %s %s %s' % (self.mount_options, shquote(dev), shquote(mp))
                else:
                    mount_cmd = 'sudo mount %s %s' % (shquote(dev), shquote(mp))

                self.run_cmd('grep -qs %s /proc/mounts || %s' % (shquote(mp), mount_cmd),
                             tgtpath='/', catchout=True)

            except CmdError as err:
                raise HostError("Can't mount %s. %s" % (mp, str(err)))

        # mount ecryptfs
        # TODO: needs testing
        for cryp, mp in self.ecryptfs_mounts.items():
            ui.print_debug("mounting ecryptfs: %s %s" % (cryp, mp))
            passphrase = self.vol_keys[mp]

            try:
                raw = self.run_cmd('sudo ecryptfs-add-passphrase -',
                                   catchout=True, stdin=passphrase)
                sig = re.search("\[(.*?)\]", raw).group(1)
                options = "no_sig_cache,ecryptfs_unlink_sigs,key=passphrase,ecryptfs_cipher=aes," + \
                          "ecryptfs_key_bytes=16,ecryptfs_passthrough=n,ecryptfs_enable_filename_crypto=y," + \
                          "ecryptfs_sig=%s,ecryptfs_fnek_sig=%s" % (sig, sig)

                mount_cmd = 'sudo mount -i -t ecryptfs -o %s %s.crypt %s' % (shquote(options),
                                                                              shquote(cryp),
                                                                              shquote(mp)),

                self.run_cmd('grep -qs %s /proc/mounts || %s' % (shquote(mp), mount_cmd),
                             tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't mount ecryptfs directory %s. %s" % (mp, str(err)))

        # mount swap
        if self.swapfile:
            ui.print_debug("mounting swap: %s" % self.swapfile)
            try:
                self.run_cmd('grep -qs %s /proc/swaps || ' % shquote(self.swapfile) + \
                             '[ ! -f %s ] || ' % shquote(self.swapfile) + \
                             'sudo swapon %s' % shquote(self.swapfile),
                             tgtpath='/', catchout=True)

            except CmdError as err:
                raise HostError("Can't mount swap %s. %s" % (self.swapfile, str(err)))


    def umount_devices(self):
        # kill systemd user session
        if self.systemd_user:
            ui.print_debug("stopping systemd --user")
            try:
                self.run_cmd('systemctl --user exit || true', tgtpath='/', catchout=True)

            except CmdError as err:
                raise HostError("Error stopping systemd --user instance. %s" % str(err))

        # umount swap
        if self.swapfile:
            ui.print_debug("umounting swap: %s" % self.swapfile)
            try:
                self.run_cmd('! grep -qs %s /proc/swaps || ' % shquote(self.swapfile) + \
                             'sudo swapoff %s' % shquote(self.swapfile),
                             tgtpath='/', catchout=True)

            except CmdError as err:
                raise HostError("Can't umount %s. %s" % (self.swapfile, str(err)))

        # umount ecryptfs
        for cryp, mp in self.ecryptfs_mounts.items():
            ui.print_debug("umounting ecryptfs: %s %s" % (cryp, mp))
            try:
                self.run_cmd('! grep -qs %s /proc/mounts || ' % shquote(mp) + \
                             'sudo umount %s' % shquote(mp),
                             tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't umount ecryptfs directory %s. %s" % (mp, str(err)))

        # umount devices
        for dev, mp in self.mounts.items():
            ui.print_debug("umounting devices: %s %s" % (dev, mp))
            try:
                self.run_cmd('! grep -qs %s /proc/mounts || ' % shquote(mp) + \
                             'sudo umount %s' % shquote(mp),
                             tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't umount %s. %s" % (mp, str(err)))

        # close luks partitions
        for dev, name in self.luks_mounts.items():
            ui.print_debug("umounting luks: %s %s" % (dev, name))
            try:
                self.run_cmd('sudo cryptsetup close --type luks %s' % shquote(name), tgtpath='/', catchout=True)
            except CmdError as err:
                raise HostError("Can't close luks partition %s. %s" % (name, str(err)))


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

        # check whether all devices are mounted
        if not check_devices():
            raise HostError("There are unmounted devices")

        # perform mount checks
        for p in self.check_mounts_list:
            path = os.path.join(self.path, p)
            if not self.path_exists(path):
                raise HostError("path %s does not exist" % path)

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
            raise HostError("Can't check disk usage. %s" % str(err))



    def run_on_dirs(self, dirs, func, action, desc=None, silent=False, dryrun=False):
        """Utility function to run a function on a set of directories.
           func(d) operates on a dir object d."""
        from async.directories import InitError, HookError, SyncError, CheckError, DirError

        failed = []
        keys = list(dirs.keys())
        num = len(keys)
        ret = True

        with self.in_state('mounted', silent=silent, dryrun=dryrun):
            st = "%s on #*m%s#*w." % (action, self.name)
            if desc: st = st + ' (%s).' % desc
            st = st + ' %s' % datetime.now().strftime("%a %d %b %Y %H:%M")
            ui.print_status(st)
            ui.print_color("")

            for i, k in enumerate(keys):
                d = dirs[k]
                if not silent: ui.print_enum(i+1, num, "%s #*y%s#t (%s)" % (action.lower(), d.name, d.type))

                try:
                    func(d)

                except (CheckError, InitError, SyncError, DirError) as err:
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
            ui.print_color("#*w%s #Gsuceeded#*w.#t" % action)
            return True

        elif len(failed) > 0:
            ui.print_color("#*w%s #Rfailed#*w.#t" % action)
            ui.print_color("  directories: %s" % ', '.join(failed))
            return False

        ui.print_color("\n")


    # Last sync state
    # ----------------------------------------------------------------


    def save_lastsync(self, path, rname, success):
        """Save sync success state"""
        lsfile = os.path.join(path, self.asynclast_file)
        now = datetime.today().isoformat()
        data = json.dumps({'remote': rname,
                           'timestamp': now,
                           'success': success,
                           'busy': False})
        try:
            self.run_cmd('echo %s > %s' % (shquote(data), shquote(lsfile)), catchout=True)
        except:
            ui.print_warning("Can't save '%s'" % path)


    def read_lastsync(self, path):
        lsfile = os.path.join(path, self.asynclast_file)

        try:
            raw = self.run_cmd('[ -f %s ] && cat %s || true' % (shquote(lsfile), shquote(lsfile)),
                               catchout=True).strip()
            ls = json.loads(raw)
            return {'remote': ls.get('remote', None),
                    'timestamp': dateutil.parser.parse(ls['timestamp']),
                    'success': ls.get('success', False),
                    'busy': ls.get('busy', False)}

        except:
            ui.print_warning("Can't read '%s'" % path)
            return {'remote': None,
                    'timestamp': None,
                    'success': False,
                    'busy': False}



    def signal_lastsync(self, path, rname):
        """Signal there is an ongoing sync"""
        lsfile = os.path.join(path, self.asynclast_file)
        now = datetime.today().isoformat()
        data = json.dumps({'remote': rname,
                           'timestamp': now,
                           'success': False,
                           'busy': True})
        try:
            self.run_cmd('echo %s > %s' % (shquote(data), shquote(lsfile)))
        except:
            ui.print_warning("Can't save '%s'" % path)



    def checkdir_lastsync(self, remote, d, opts):
        """Check whether last sync failed on a different host"""

        from async.directories.base import SyncError, SkipError

        local = self

        lls = local.read_lastsync(d.fullpath(local))
        rls = remote.read_lastsync(d.fullpath(remote))

        # fail if an ongoing sync
        if lls['busy']:
            raise SkipError("There is an ongoing sync on %s" % local.name)

        if rls['busy']:
            raise SkipError("There is an ongoing sync on %s" % remote.name)

        # only sync if last sync failed
        if opts.failed:
            if lls['success']:
                raise SkipError("last sync succeeded")

        # only sync if older than opts.older
        if opts.older > 0:
            threshold = datetime.today() - timedelta(minutes=opts.older)
            if lls['timestamp'] and lls['timestamp'] > threshold:
                raise SkipError("last sync less than %d minutes ago" % opts.older)

        # only sync if last sync failed or done from a different host
        if opts.needed:
            if lls['success'] and rls['success'] and lls['remote'] == remote.name and rls['remote'] == local.name:
                raise SkipError("successful last sync from the same host")

        # fail if last sync failed from a different host
        if not opts.force and d.lastsync:
            if not lls['success'] and lls['remote'] != remote.name:
                raise SyncError("failed last sync on '%s' from a different host. Use the --force" % local.name)

            if not rls['success'] and rls['remote'] != local.name:
                raise SyncError("failed last sync on '%s' from a different host. Use the --force" % remote.name)

        return True



    # Interface
    # ----------------------------------------------------------------

    def start(self, silent=False, dryrun=False):
        """Starts the host if not running"""
        st = 'online'
        ret = True

        try:
            if self.STATES.index(self.state) < self.STATES.index('online'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def stop(self, silent=False, dryrun=False):
        """Stops the host if running"""
        st = 'offline'
        ret = True
        try:
            with self.in_state(silent=silent, dryrun=dryrun):
                if self.STATES.index(self.state) >= self.STATES.index('online'):
                    ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def mount(self, silent=False, dryrun=False):
        """Mounts partitions on host, starting it if necessary"""
        st = 'mounted'
        ret = True
        try:
            with self.in_state(silent=silent, dryrun=dryrun):
                if self.STATES.index(self.state) < self.STATES.index('mounted'):
                    ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def umount(self, silent=False, dryrun=False):
        """Umounts partitions on host if mounted"""
        st = self.STATES[self.STATES.index('mounted') - 1]
        ret = True
        try:
            with self.in_state(silent=silent, dryrun=dryrun):
                if self.STATES.index(self.state) >= self.STATES.index('mounted'):
                    ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def print_status(self, state=None, silent=False, dryrun=False):
        """Prints a host status information"""
        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):
                info = self.get_info()

                ui.print_status("Status of #*m%s#t" % self.name)
                ui.print_color("")

                if 'state' in info: ui.print_color('   #*wstate:#t %s' % info['state'])

                if 'ami_name' in info and 'ami_id' in info:
                    ui.print_color('     #*wami:#t %s (%s)' % (info['ami_id'],
                                                               info['ami_name']))

                if 'instance' in info and 'itype' in info:
                    ui.print_color('    #*winst:#t %s (%s)' % (info['instance'],
                                                               info['itype']))

                if 'block' in info:
                    ui.print_color('   #*wblock:#t %s' % ', '.join(
                        ['%s (%s)' % (k, s) for k, s in info['block'].items()]))

                if 'host' in info:
                    ui.print_color('    #*whost:#t %s' % info['host'])

                if 'ip' in info:
                    ui.print_color('      #*wip:#t %s' % info['ip'])

                if 'size' in info:
                    ui.print_color('    #*wsize:#t %s' % number2human(1024*info['size'], suffix='b'))

                if 'free' in info:
                    ui.print_color('    #*wfree:#t %3.2f%%' % (100 * float(info['free']) / float(info['size'])))

                ui.print_color("")

        except HostError as err:
            ui.print_error(str(err))

        return True


    def print_log(self, state=None, silent=False, dryrun=False, opts=None):
        """Prints host logs"""
        if self.log_cmd == None:
            ui.print_error("Log retrieval not implemented for host %s" % self.name)
            return False

        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):
                if not dryrun:
                    raw = self.run_cmd(self.log_cmd, tgtpath='/', catchout=True)
                    cmd.pager(raw)
                    return True

        except HostError as err:
            ui.print_error(str(err))


    def print_dirstate(self, state=None, silent=False, dryrun=False, opts=None):
        """Prints the state of directories in a host"""
        dirs = self._get_common_dirs(self, self, dirs=opts.dirs, ignore=opts.ignore)
        keys = sorted(dirs.keys())

        types={
            'local' : '#Mlocal#t',
            'unison': '#Yunison#t',
            'rsync' : '#Yrsync#t',
            'annex' : '#Gannex#t',
            'git'   : '#Bgit#t',
        }

        if opts: slow = opts.slow
        else:    slow = True

        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):
                ui.print_color("Directories on #*y%s#t (%s)\n" % (self.name, self.path))
                for k in keys:
                    d = dirs[k]
                    status = d.status(self, slow=slow)

                    if status['ls-success'] == None:    lastsync=' #G?#t '
                    elif status['ls-success'] == False: lastsync=' #RX#t '
                    elif status['ls-success'] == True:  lastsync=' #G√#t '

                    if status['ls-timestamp']: timestamp=status['ls-timestamp'].strftime('%d %b %H:%M:%S')
                    else:                      timestamp=""

                    nameperms = '#*b{0[relpath]:<10}#t   #G{0[perms]} #Y{0[user]:<10}#t'.format(status)

                    # directory type
                    dirtype = ''
                    if status['path']:
                        dirtype = '{0:<15}'.format(types[status['type']])
                    else:
                        dirtype = '{0:<15}'.format('#Rgone!#t')

                    # number of files
                    numfiles = '--'
                    if 'numfiles' in status:
                        numfiles = number2human(status['numfiles'], fmt='%(value).3G %(symbol)s')

                    numchanged = ''
                    if 'changed' in status:
                        numchanged = number2human(status.get('changed', 0) + status.get('staged', 0),
                                                  fmt='%(value).3G %(symbol)s')

                    nummissing = ''
                    if 'missing' in status:
                        nummissing = number2human(status['missing'], fmt='%(value).3G %(symbol)s')

                    numunused = ''
                    if 'unused' in status:
                        numunused = number2human(status['unused'], fmt='%(value).3G %(symbol)s')

                    # git status
                    if status['type'] == 'annex' or status['type'] == 'git':
                        if status['conflicts'] > 0:  symstate = '#RX#t '
                        elif status['changed'] > 0:  symstate = '#R*#t '
                        elif status['staged'] > 0:   symstate = '#G*#t '
                        else:                        symstate = '#G√#t '
                    else:
                        symstate = '  '

                    # annex status
                    dirstate = '                 '
                    if status['type'] == 'annex':
                        dircounts = '[#R%s#t/#G%s#t]' % (nummissing, numunused)
                        dirstate  = '{0:>8} {1}'.format(numfiles, dircounts)
                        dclen = len('[%s/%s]' % (nummissing, numunused))

                    else:
                        dirstate = '{0:>8} {1}'.format(numfiles, '')
                        dclen=0

                    dirstate = dirstate + (10 - dclen)*' '

                    ui.print_color(lastsync + nameperms + symstate + dirtype + dirstate + timestamp)

                print("")

        except HostError as err:
            ui.print_error(str(err))

        return True



    def shell(self, state=None, silent=False, dryrun=False):
        """Opens a shell to host"""
        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):

                ui.print_color("")
                ret = self.interactive_shell()
                if ret != 0:
                    ui.print_error("Shell returned with code %d" % ret)
                ui.print_color("")

        except HostError as err:
            ui.print_error(str(err))



    def cmd(self, cmd, state=None, silent=False, dryrun=False):
        """Runs a command on the host"""
        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):

                ui.print_color("")
                self.run_cmd(cmd, tgtpath="$HOME")

        except HostError as err:
            ui.print_error(str(err))

        except CmdError as err:
            ui.print_error("Command error on %s. %s" % (self.name, str(err)))



    def run(self, script, state=None, silent=False, dryrun=False):
        """Runs a local script on the host"""
        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):

                ui.print_color("")
                self.run_script(script, tgtpath="$HOME")

        except HostError as err:
            ui.print_error(str(err))

        except CmdError as err:
            ui.print_error("Command error on %s. %s" % (self.name, str(err)))



    def backup(self, state=None, silent=False, dryrun=False):
        """Creates a data backup"""
        raise NotImplementedError



    def snapshot(self, state=None, silent=False, dryrun=False):
        """Creates a server backup"""
        raise NotImplementedError



    def upgrade(self, state=None, silent=False, dryrun=False, opts=None):
        """Update host"""
        if self.update_cmd == None:
            ui.print_error("System update not implemented for host %s" % self.name)
            return False

        try:
            with self.in_state(state, silent=silent, dryrun=dryrun):
                if not dryrun:
                    self.run_cmd(self.update_cmd, tgtpath='/', catchout=False)
                    return True

        except HostError as err:
            ui.print_error(str(err))



    def sync(self, remote, silent=False, dryrun=False, opts=None):
        raise NotImplementedError



    def init(self, silent=False, dryrun=False, opts=None):
        """Prepares a host for the initial sync. sets up directories, and git annex repos"""
        dirs = self._get_common_dirs(self, self, dirs=opts.dirs, ignore=opts.ignore)

        try:
            def func(d):
                d.init(self, silent=silent or opts.terse, dryrun=dryrun, opts=opts)

            return self.run_on_dirs(dirs, func, "Init", silent=silent, dryrun=dryrun)

        except HostError as err:
            ui.print_error(str(err))
            return False



    def check(self, silent=False, dryrun=False, opts=None):
        """Check directories for local machine"""
        dirs = self._get_common_dirs(self, self, dirs=opts.dirs, ignore=opts.ignore)

        try:
            def func(d):
                d.check(self, silent=silent or opts.terse, dryrun=dryrun, opts=opts)

            return self.run_on_dirs(dirs, func, "Check", silent=silent, dryrun=dryrun)

        except HostError as err:
            ui.print_error(str(err))
            return False



    # Filesystem manipulations
    # ----------------------------------------------------------------

    def symlink(self, tgt, path, force=False):
        try:
            if force and self.path_exists(path):
                self.run_cmd('rm -Rf %s' % shquote(path))
            self.run_cmd('ln -s %s %s' % (shquote(tgt), shquote(path)))

        except CmdError as err:
            raise HostError("Can't create symlink on %s. %s" % (self.name, str(err)))


    def path_exists(self, path):
        """Returns true if given path exists"""
        try:
            self.run_cmd('[ -e %s ]' % shquote(path), tgtpath='/')
            return True
        except CmdError as err:
            return False


    def realpath(self, path):
        """Returns the real path after dereferencing symlinks, or none if dangling"""
        try:
            rp = self.run_cmd('realpath %s' % shquote(path), tgtpath='/', catchout=True)
            return rp.strip()
        except CmdError as err:
            return None


    def mkdir(self, path, mode):
        try:
            self.run_cmd('mkdir -m %o %s' % (mode, shquote(path)))
        except CmdError as err:
            raise HostError("Can't create directory on %s. %s" % (self.name, str(err)))


    def chmod(self, path, mode):
        try:
            self.run_cmd('chmod %o %s' % (mode, shquote(path)))
        except CmdError as err:
            raise HostError("Can't chmod directory on %s. %s" % (self.name, str(err)))



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


    def in_state(self, tgtstate=None, silent=False, dryrun=False):
        """Returns a controller to be used in with statements"""
        return HostController(self, tgtstate=tgtstate, silent=silent, dryrun=dryrun)


    def set_state(self, state, silent=False, dryrun=False):
        """Sets the host to the given state, passing through all the states in between."""
        self.state = self.get_state()
        if state == 'unknown': return state

        ui.print_debug("set_state. %s --> %s" % (self.state, state))

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


    def run_cmd(self, cm, tgtpath=None, catchout=False, stdin=None, silent=False):
        """Run a shell command in a given path at host"""
        raise NotImplementedError


    def interactive_shell(self):
        """Opens an interactive shell to host. Returns the shell return code"""
        raise NotImplementedError


    def run_script(self, scrpath, tgtpath=None, catchout=False, silent=False):
        """Run a script in a local path on the host"""

        try:
            with open(scrpath, 'r') as fd:
                script=fd.read()
                ret = self.run_cmd("bash -s", tgtpath=tgtpath, catchout=catchout, stdin=script, silent=silent)

        except IOError as err:
            raise HostError("Can't run script '%s' on %s host" % (scrpath, self.name))


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
