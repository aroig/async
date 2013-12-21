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


import sys
import re
import os
import subprocess

from optparse import OptionParser

from async import __version__
from async.config import AsyncConfig, AsyncConfigError

import async.archui as ui
from async import get_remote_host, get_local_host

from async.hosts import Ec2Host, HostError



# Functions
#------------------------

def get_itype(name):
    if name == "micro":    return "t1.micro"
    elif name == "small":  return "m1.small"
    elif name == "medium": return "m1.medium"
    elif name == "large":  return "m1.large"
    else:                  return name


def setup_tee(logfile):
    """redirect stdout and stderr through tee"""
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)

    proc = subprocess.Popen(["tee", logfile], stdin=subprocess.PIPE)
    os.dup2(proc.stdin.fileno(), sys.stdout.fileno())
    os.dup2(proc.stdin.fileno(), sys.stderr.fileno())


class FileSnitch(object):
    """A wrapper for stdout that writes everything to a logfile"""
    def __init__(self, orig, logfile):
        self.logfile = open(logfile, 'w')
        self.orig = orig

    def write(self, data):
        self.logfile.write(data)
        self.orig.write(data)

    def flush(self):
        self.orig.flush()

    def close():
        self.logfile.close()
        self.orig.close()



# Main stuff
#------------------------

usage = """Usage: %prog [options] <cmd> <host>

Commands:
  status:     %prog status <host>
              Print host status.

     ls:      %prog host <host>
              Print state data for directories.

  sync:       %prog sync <host>
              Sync host.

  init:       %prog init <host>
              Initialize directory structure on host.

  check:      %prog check <host>
              Checks directory structure on host.

  shell:      %prog shell <host>
              Launch an interactive shell on host.

  run:        %prog run <host> <script>
              Run a local script on host

  start:      %prog start <host>
              Start the host.

  stop:       %prog start <host>
              Stop the host.

  mount:      %prog mount <host>
              Mount devices on host.

  umount:     %prog umount <host>
              Umount devices on host.

  launch:     %prog launch <host>
              Launch an ec2 instance.

  terminate:  %prog terminate <host>
              Terminate an ec2 instance.

  snapshot:   %prog snapshot <host>
              Create a snapshot of a running ec2 instance.


"""
parser = OptionParser(usage=usage)

parser.add_option("-b", "--batch", dest="batch", action="store_true", default=False,
                  help="Asks no questions.")

parser.add_option("-s", "--slow", action="store_true", default=False, dest="slow",
                  help="Disables fastcheck, checking every file. Much slower.")

parser.add_option("-a", "--auto", action="store_true", default=False, dest="auto",
                  help="Assume default action if there are no conflicts.")

parser.add_option("-f", "--force", action="store", type="string", default=None, dest="force",
                  help="Values: up, down. Forces to transfer everything up or down.")

parser.add_option("-d", "--dirs", action="store", type="string", default=None, dest="dirs",
                  help="Only sync the dirs given as a comma separated list.")

parser.add_option("--ignore", action="store", type="string", default=None, dest="ignore",
                  help="Ignore these paths, given as a comma separated list.")

parser.add_option("-i", "--instance", action="store", type="string", default=None, dest="itype",
                  help="Instance type. Values: micro (default), small, large")

parser.add_option("--terse", dest="terse", action="store_true", default=False,
                  help="Terse output.")

parser.add_option("--quiet", dest="quiet", action="store_true", default=False,
                  help="No output.")

parser.add_option("--dryrun", dest="dryrun", action="store_true", default=False,
                  help="Dry run.")

parser.add_option("--debug", dest="debug", action="store_true", default=False,
                  help="Debug mode.")

parser.add_option("--version", action="store_true", default=False, dest="version",
                  help="Print version and exit")


(opts, args) = parser.parse_args()

if opts.version:
    print(__version__)
    sys.exit(0)

if opts.dirs:
    opts.dirs = [d.strip() for d in opts.dirs.split(',') if len(d.strip()) > 0]

if opts.ignore:
    opts.ignore = [d.strip() for d in opts.ignore.split(',') if len(d.strip()) > 0]
else:
    opts.ignore = []

try:
    # parse config
    conf = AsyncConfig(os.path.expandvars('$HOME/.config/async/'))

    # UI settings
    if opts.debug: ui.set_debug(1)
    if conf.async['color'] != None: ui.use_color(conf.async['color'])

    # If the output is not a terminal, remove the colors
    if not sys.stdout.isatty(): ui.use_color(False)

    # extract command and hostname
    if len(args) > 0:
        cmd = args[0]
    else:
        ui.print_error("Need a command")
        sys.exit(1)

    # get local and remote hosts
    local = get_local_host(conf)

    if len(args) > 1:
        name = args[1]
        remote = get_remote_host(name, conf)

    else:
        ui.print_error("Need a host")
        sys.exit(1)

    logging_cmds = set(['init', 'sync'])
    if cmd in logging_cmds and conf.async['logfile'] != None:
        # setup_tee(conf.async['logfile'])
        ui.start_logging(conf.async['logfile'], level=4)


    args = args[2:]
    ret = True
    if cmd == "status":
        if len(args) == 0:    ret = remote.print_status()
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "ls":
        if len(args) == 0:    ret = remote.print_dirstate(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "sync":
        if len(args) == 0:    ret = local.sync(remote=remote, dryrun=opts.dryrun,
                                               silent=opts.quiet, opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "init":
        if len(args) == 0:    ret = remote.init(dryrun=opts.dryrun,
                                                silent=opts.quiet, opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "check":
        if len(args) == 0:    ret = remote.check(dryrun=opts.dryrun,
                                                 silent=opts.quiet, opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "start":
        if len(args) == 0:    ret = remote.start(dryrun=opts.dryrun,
                                                 silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "stop":
        if len(args) == 0:    ret = remote.stop(dryrun=opts.dryrun,
                                                silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "mount":
        if len(args) == 0:    ret = remote.mount(dryrun=opts.dryrun,
                                                 silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "umount":
        if len(args) == 0:    ret = remote.umount(dryrun=opts.dryrun,
                                                  silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "shell":
        if len(args) == 0:    ret = remote.shell(dryrun=opts.dryrun,
                                                 silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "run":
        if len(args) == 1:    ret = remote.run(script=args[0], dryrun=opts.dryrun,
                                               silent=opts.quiet)
        elif len(args) == 0:  ui.print_error("Missing script.")
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "ping":
        if len(args) == 0:    ret = remote.ping()
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "launch":
        if not isinstance(remote, Ec2Host):
            ui.print_error("Host %s is not an Ec2 host" % remote.name)

        elif len(args) == 0:
            ret = remote.launch(dryrun=opts.dryrun, silent=opts.quiet,
                                itype=get_itype(opts.itype))

        else:
            ui.print_error("Too many arguments.")

    elif cmd == "terminate":
        if not isinstance(remote, Ec2Host):
            ui.print_error("Host %s is not an Ec2 host" % remote.name)

        elif len(args) == 0:
            ret = remote.terminate(dryrun=opts.dryrun, silent=opts.quiet)

        else:
            ui.print_error("Too many arguments.")

    elif cmd == "snapshot":
        if not isinstance(remote, Ec2Host):
            ui.print_error("Host %s is not an Ec2 host" % remote.name)

        elif len(args) == 0:  ret = remote.snapshot(dryrun=opts.dryrun, silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")


    elif cmd == "upgrade":
        if len(args) == 0:    ret = remote.upgrade(dryrun=opts.dryrun, silent=opts.quiet)
        else:                 ui.print_error("Too many arguments.")

    else:
        ui.print_error("Unknown command %s" % cmd)
        sys.exit(1)


    if cmd in logging_cmds and conf.async['logfile'] != None:
        ui.start_logging(conf.async['logfile'], level=4)


    if ret: sys.exit(0)
    else:   sys.exit(1)

except AsyncConfigError as err:
    ui.print_error("invalid config: %s" % str(err))

except KeyboardInterrupt:
    print("")
    sys.exit(0)

except EOFError:
    print("")
    sys.exit(1)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
