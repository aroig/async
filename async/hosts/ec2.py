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

from async.hosts.ssh import SshHost

class Ec2Host(SshHost):
    """An ec2 instance"""

    def __init__(self, conf):

        # base config
        super(Ec2Host, self).__init__(conf)

        self.type = 'ec2'

        # ssh related config
        self.hostname         = conf['hostname']         # the hostname






# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
