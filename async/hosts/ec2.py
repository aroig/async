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
    # ordered list of states. terminate does not belong here as it destroys the instance.
    STATES = ['offline', 'online', 'attached', 'mounted']

    def __init__(self, conf):

        # base config
        super(Ec2Host, self).__init__(conf)

        # ec2 config
        self.ec2_ami = conf['instance']['ec2_ami']
        self.ec2_itype = conf['instance']['ec2_itype']
        self.ec2_owner = conf['instance']['ec2_owner']

        self.ec2_keypair        = conf['instance']['ec2_keypair']
        self.ec2_security_group = conf['instance']['ec2_security_group']

        # open aws connection
        ec2_region = conf['instance']['ec2_region']
        aws_keys = self.read_keys(conf['instance']['aws_keys'])
        self.conn = ec2.connect_to_region(region_name = ec2_region,
                                          aws_access_key_id = aws_keys['access_key_id'],
                                          aws_secret_access_key = aws_keys['secret_access_key'])

        if not self.conn:
            raise Ec2Error("Could not establish a connection with aws.")

        self.load_volumes()
        self.load_ami()
        self.load_instance()


    # Utilities
    # ----------------------------------------------------------------

    def detach_volume(self, vol):
        vol.detach()
        # TODO: wait for it


    def attach_volume(self, vol, inst, dev):
        vol.attach(inst, dev)
        # TODO: wait for it




    # status functions
    # ------------------------------------------------------

    def create_instance(self):
        """Creates a new instance"""
        res = self.conn.run_instances(min_count = 1, max_count = 1,
                                      image_id = self.ami.id,
                                      key_name = self.ec2_keypair,
                                      security_groups = [self.ec2_security_group],
                                      instance_type = self.ec2_itype,
                                      placement = self.zone)

        if len(res.instances) == 0:
            raise Ec2Error("Something happened. Instance not launched.")
        elif len(res.instances) >= 2:
            raise Ec2Error("Something happened. Too many instances launced.")

        self.instance = res.instances[0]


    def load_instance(self):
        """Updates running instance"""
        L = [ins for res in self.conn.get_all_instances() for ins in res.instances
             if ins.image_id == self.ami.id and ins.state != 'terminated']
        if len(L) == 0:
            self.instance = None
        elif len(L) >= 2:
            raise Ec2Error("Found several instances of %s running" % self.ec2_ami)
        else:
            self.instance = L[0]


    def load_ami(self):
        L = [a for a in self.conn.get_all_images(owners = self.ami_owner)
             if self.ec2_ami == a.name]
        if len(L) == 0:
            raise Ec2Error("Ami %s not found" % self.ec2_ami)
        elif len(L) >= 2:
            raise Ec2Error("Found several ami's with name %s" % self.ec2_ami)
        else:
            self.ami = L[0]


    def load_volumes(self):
        self.volumes = {}
        for dev, vol in conf['instance']['volumes']:
            L = self.conn.get_all_volumes(volume_ids = [col])
            if len(L) == 0:
                raise Ec2Error("Can't fine volume %s" % vol)
            elif len(L) >= 2:
                raise Ec2Error("Found several volumes with id %s" % vol)
            else:
                self.volumes[dev] = L[0]


    def check_ami(self):
        """Returns true if the ami is available"""
        self.ami.update()
        if self.ami: return self.ami.state == 'available'
        else:        return False


    def check_instance(self):
        """Returns true if there is an instance running"""
        self.instance.update()
        if self.instance: return self.instance.state == 'running'
        else:             return False


    def check_volumes(self):
        """Returns true if all the volumes are attached"""
        attached = True
        for dev, vol in self.volumes.items():
            vol.update()
            if not vol.attachment_state() == 'attached':
                attached = False
        return attached


    def host(self):
        if self.instance: return self.instance.public_dns_name
        else:             return None


    def ip(self):
        if self.instance: return self.instance.ip_address
        else:             return None


    # Interface
    # ----------------------------------------------------------------


    def launch(self, silent=False, dryrun=False):
        """Launches a new instance"""
        # TODO: call create_instance if no instance exists

    def terminate(self, silent=False, dryrun=False):
        """Terminates the current instance"""
        if self.STATES.index(self.state) > self.STATES.index('terminated'):
            self.set_state('terminated', silent=silent, dryrun=dryrun)

    def attach(self, silent=False, dryrun=False):
        """Attaches volumes"""
        if self.STATES.index(self.state) < self.STATES.index('attached'):
            self.set_state('attached', silent=silent, dryrun=dryrun)

    def detach(self, silent=False, dryrun=False):
        """Deataches volumes"""
        if self.STATES.index(self.state) >= self.STATES.index('attached'):
            self.set_state('detached', silent=silent, dryrun=dryrun)


    # State transitions
    # ----------------------------------------------------------------
    # TODO:waitings

    def enter_state(self, state):
        if state == 'terminated':
            pass

        elif state == 'offline':
            pass

        elif state == 'online':
            self.conn.start_instances([self.instance.id])

        elif state == 'attached':
            for dev, vol in self.volumes.items():
                self.attach_volume(vol, self.instance.id, dev)

        elif state == 'mounted':
            self.mount_devices()

        else:
            raise HostError("Unknown state %s" % state)


    def leave_state(self, state):
        if state == 'terminated':
            pass

        elif state == 'offline':
            self.conn.terminate_instances([self.instance.id])

        elif state == 'online':
            self.conn.stop_instances([self.instance.id])

        elif state == 'attached':
            for dev, vol in self.volumes.items():
                self.detach_volume(vol)

        elif state == 'mounted':
            self.umount_devices()

        else:
            raise HostError("Unknown state %s" % state)



    # Implementation
    # ----------------------------------------------------------------

    def get_state(self):
        """Queries the state of the host"""
        # TODO
        # NOTE: must change self.state
        pass


    def get_info(self):
        """Gets a dictionary with host state parameters"""

        info = super(Ec2Host, self).get_info()

        if self.ami:
            info['ami_name'] = self.ami.name
            info['ami_id'] = self.ami.id

        if self.instance:
            info['instance'] = self.instance.status
            info['itype'] = self.instance.instance_type



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
