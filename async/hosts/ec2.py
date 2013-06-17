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
from boto import ec2

class Ec2Error(Exception):
    def __init__(self, msg=None):
        super(self, Ec2Error).__init__(msg)


class Ec2Host(SshHost):
    """An ec2 instance"""

    def __init__(self, conf):

        # base config
        super(Ec2Host, self).__init__(conf)

        self.type = 'ec2'

        # ec2 config
        self.ec2_ami = conf['instance']['ec2_ami']
        self.ec2_itype = conf['instance']['ec2_itype']
        self.ec2_owner = conf['instance']['ec2_owner']

        # open aws connection
        ec2_region = conf['instance']['ec2_region']
        aws_keys = self.read_keys(conf['instance']['aws_keys'])
        self.conn = ec2.connect_to_region(region_name = ec2_region,
                                          aws_access_key_id = aws_keys['access_key_id'],
                                          aws_secret_access_key = aws_keys['secret_access_key'])

        if not self.conn:
            raise Ec2Error("Could not establish a connection with aws.")

        # load volumes
        self.volumes = {}
        for dev, vol in conf['instance']['volumes']:
            L = self.conn.get_all_volumes(volume_ids = [col])
            if len(L) == 0:
                raise Ec2Error("Can't fine volume %s" % vol)
            elif len(L) >= 2:
                raise Ec2Error("Found several volumes with id %s" % vol)
            else:
                self.volumes[dev] = L[0]

        # load ami
        L = [a for a in self.conn.get_all_images(owners = self.ami_owner)
             if self.ec2_ami == a.name]
        if len(L) == 0:
            raise Ec2Error("Ami %s not found" % self.ec2_ami)
        elif len(L) >= 2:
            raise Ec2Error("Found several ami's with name %s" % self.ec2_ami)
        else:
            self.ami = L[0]

        # load running instance
        L = [ins for res in self.conn.get_all_instances() for ins in res.instances
             if ins.image_id == self.ami.id and ins.state != 'terminated']
        if len(L) == 0:
            self.instance = None
        elif len(L) >= 2:
            raise Ec2Error("Found several instances of %s running" % self.ec2_ami)
        else:
            self.instance = L[0]


    # Utilities
    # ----------------------------------------------------------------



    # Interface
    # ----------------------------------------------------------------

    def terminate(self, silent=False, dryrun=False):
        """Stops the host"""
        if not self.get_state() in set(['terminated']):
            self.switch_state("Terminating %s" % (self.name), 'terminated', silent=silent, dryrun=dryrun)


    def attach(self):
        """Attaches volumes"""
        for dev, vol in self.volumes.items():
            vol.attach(self.instance.id, dev)
            # TODO: wait for it


    def detach(self):
        """Deataches volumes"""
        for dev, vol in self.volumes.items():
            vol.detach()
            # TODO: wait for it


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



    # backup
    # ------------------------------------------------------

    def make_ami_snapshot(self, name, desc):
        """Creates a snapshot of the running image."""
        self.update()

        if self.skynet_status() != 'running':
            raise InstanceError("Instance is not running.")

        self.conn.create_image(instance_id = self.instance.id,
                               name = name,
                               description = desc)

        if not self._wait_for('available', self.ami_status, timeout=300):
            raise InstanceError("I've waited long enough and the ami is not created.")


    def make_data_snapshot(self, desc):
        """Creates a snapshot of the data volume."""
        self.update()

        if self.skynet_status() != 'running':
            raise InstanceError("Instance is not running.")

        self.conn.create_snapshot(volume_id = self.data.id,
                                  description = desc)





# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
