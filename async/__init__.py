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

__version__ = "0.1"


from async.hosts import Ec2Host, SshHost, DirectoryHost, LocalHost
import async.archui as ui
import socket


def get_remote_host(hostname, conf):
    if hostname in conf.host:
        hconf = conf.host[hostname]
        typ = conf.host[hostname]['type']
        if typ == 'ec2':
            return Ec2Host(conf=hconf)

        elif typ == 'ssh':
            return SshHost(conf=hconf)

        elif typ == 'directory':
            return DirectoryHost(conf=hconf)

        else:
            ui.print_error("Unknown host type %s (%s)" % (typ, hostname))
            sys.exit(1)

    elif hostname == 'localhost':
        return get_localhost(conf)

    else:
        ui.print_error("Unknown host: %s" % hostname)
        sys.exit(1)



def get_local_host(conf):
    localhostname = socket.getfqdn()
    local = None
    for k, h in conf.host.items():
        if h['hostname'] == localhostname:
            return LocalHost(conf.host[k])

    ui.print_error("Local host %s not configured" % localhostname)
    sys.exit(1)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
