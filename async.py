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
from configparser import ConfigParser

from async import __version__
from async import Host
from async import ui



# Main stuff
#------------------------

usage = """Usage: %prog [options]
"""
parser = OptionParser(usage=usage)

parser.add_option("-b", "--batch", dest="batch", action="store_true", default=False,
                  help="Asks no questions.")

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


try:
    # parse config
    conf = ConfigParser()
    conf.read([os.path.expandvars('$XDG_CONFIG_HOME/async/async.conf')])

    # UI settings
    if opts.debug: ui.set_debug()
    ui.use_color(conf.getboolean('async', 'color'))

    # If the output is not a terminal, remove the colors
    if not sys.stdout.isatty(): ui.use_color(False)

    # extract command and hostname
    cmd      = args[0]
    hostname = args[1]
    args     = args[2:]


    host = Host(hostname, conf)

    if cmd == "status":
        if len(args) == 0:    host.status(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "sync":
        if len(args) == 0:    host.sync(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "upgrade":
        if len(args) == 0:    host.upgrade(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "start":
        if len(args) == 0:    host.start(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "stop":
        if len(args) == 0:    host.stop(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "login":
        if len(args) == 0:    host.login(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "mount":
        if len(args) == 0:    host.mount(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    elif cmd == "umount":
        if len(args) == 0:    host.umount(opts=opts)
        else:                 ui.print_error("Too many arguments.")

    else:
        ui.print_error("Unknown command %s" % cmd)


except KeyboardInterrupt:
    print("")
    sys.exit()

except EOFError:
    print("")
    sys.exit()


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
