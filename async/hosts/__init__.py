#!/usr/bin/env python
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

from async.hosts.ec2 import Ec2Host
from async.hosts.ssh import SshHost
from async.hosts.directory import DirectoryHost
from async.hosts.local import LocalHost

from async.hosts.base import HostError
from async.hosts.base import CmdError
from async.hosts.ssh import SshError



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
