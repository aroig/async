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

from optparse import OptionParser

from async import __version__
from async.config import AsyncConfig

import async.archui as ui
from async import get_host, get_localhost



# Main stuff
#------------------------

usage = """Usage: %prog [options] cmd host
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
    opts.dirs = [d.strip() for d in opts.dirs.split(',')]


try:
    # parse config
    conf = AsyncConfig(os.path.expandvars('$HOME/.config/async/'))

    # UI settings
    if opts.debug: ui.set_debug(1)
    ui.use_color(conf.async['color'])

    # If the output is not a terminal, remove the colors
    if not sys.stdout.isatty(): ui.use_color(False)

    # extract command and hostname
    cmd = args[0]

    # get local and remote hosts
    local = get_localhost(conf)

    if len(args) > 1:
        remote = get_host(args[1], conf)
        remote.connect()
    else:
        remote = None

    args = args[2:]
    ret = 0
    if cmd == "status":
        if len(args) == 0:    ret = remote.print_status()
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "sync":
        if len(args) == 0:    ret = local.sync(remote=remote, opts=opts, dryrun=opts.dryrun)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "start":
        if len(args) == 0:    ret = remote.start(dryrun=opts.dryrun)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "stop":
        if len(args) == 0:    ret = remote.stop(dryrun=opts.dryrun)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "mount":
        if len(args) == 0:    ret = remote.mount(dryrun=opts.dryrun)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "umount":
        if len(args) == 0:    ret = remote.umount(dryrun=opts.dryrun)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "shell":
        if len(args) == 0:    ret = remote.shell()
        else:                 ui.print_error("Too many arguments.")


    elif cmd == "upgrade":
        if len(args) == 0:    ret = remote.upgrade(opts=opts)
        else:                 ui.print_error("Too many arguments.")


    else:
        ui.print_error("Unknown command %s" % cmd)
        sys.exit(1)

    sys.exit(ret)


except KeyboardInterrupt:
    print("")
    sys.exit(0)

except EOFError:
    print("")
    sys.exit(1)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
