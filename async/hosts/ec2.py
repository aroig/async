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

        self.ec2_ami = conf['instance']['ec2_ami']
        self.ec2_itype = conf['instance']['ec2_itype']
        self.ec2_region = conf['instance']['ec2_region']
        self.ec2_owner = conf['instance']['ec2_owner']

        self.attach = conf['instance']['attach']

    # Utilities
    # ----------------------------------------------------------------



    # Interface
    # ----------------------------------------------------------------

    def terminate(self, silent=False, dryrun=False):
        """Stops the host"""
        if not self.get_state() in set(['terminated']):
            self.switch_state("Terminating %s" % (self.name), 'terminated', silent=silent, dryrun=dryrun)



    # Implementation
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





# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
