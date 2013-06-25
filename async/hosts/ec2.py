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

import async.archui as ui
import async.cmd as cmd


class Ec2Error(Exception):
    def __init__(self, msg=None):
        super(Ec2Error, self).__init__(msg)


class Ec2Host(SshHost):
    """An ec2 instance"""
    # ordered list of states. terminate does not belong here as it destroys the instance.
    STATES = ['offline', 'online', 'attached', 'mounted']

    def __init__(self, conf):
        ui.print_debug("begin Ec2Host.__init__")

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

        self.load_volumes(conf['instance']['volumes'])
        self.load_ami()
        self.load_instance()


    # Utilities
    # ----------------------------------------------------------------

    def detach_volume(self, vol):
        try:
            vol.detach()
        except boto.exception.EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            return vol.attachment_state()

        if not self.wait_for('detached', _state):
            raise HostError("Timed out detaching")



    def attach_volume(self, vol, inst, dev):
        try:
            vol.attach(inst, dev)
        except boto.exception.EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            vol.update()
            return vol.attachment_state()

        if not self.wait_for('attached', _state):
            raise HostError("Timed out attaching")


    def start_instance(self, id):
        try:
            self.conn.start_instances([id])
        except boto.exception.EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            self.instance.update()
            return self.instance.state

        if not self.wait_for('running', _state):
            raise HostError("Timed out starting instance")


    def stop_instance(self, id):
        try:
            self.conn.stop_instances([id])
        except boto.exception.EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            self.instance.update()
            return self.instance.state

        if not self.wait_for('stopped', _state):
            raise HostError("Timed out stopping instance")


    def create_instance(self, itype):
        """Creates a new instance"""
        try:
            res = self.conn.run_instances(min_count = 1, max_count = 1,
                                          image_id = self.ami.id,
                                          key_name = self.ec2_keypair,
                                          security_groups = [self.ec2_security_group],
                                          instance_type = itype,
                                          placement = self.zone)

        except boto.exception.EC2ResponseError as err:
            raise HostError(str(err))

        if len(res.instances) == 0:
            raise Ec2Error("Something happened. Instance not launched.")
        elif len(res.instances) >= 2:
            raise Ec2Error("Something happened. Too many instances launced.")

        self.instance = res.instances[0]

        def _state():
            self.instance.update()
            return self.instance.state

        if not self.wait_for('running', _state):
            raise HostError("Timed out launching instance")




    # status functions
    # ------------------------------------------------------

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
        L = [a for a in self.conn.get_all_images(owners = self.ec2_owner)
             if self.ec2_ami == a.name]
        if len(L) == 0:
            raise Ec2Error("Ami %s not found" % self.ec2_ami)
        elif len(L) >= 2:
            raise Ec2Error("Found several ami's with name %s" % self.ec2_ami)
        else:
            self.ami = L[0]


    def load_volumes(self, conf):
        self.volumes = {}
        for dev, vol in conf.items():
            L = self.conn.get_all_volumes(volume_ids = [vol])
            if len(L) == 0:
                raise Ec2Error("Can't fine volume %s" % vol)
            elif len(L) >= 2:
                raise Ec2Error("Found several volumes with id %s" % vol)
            else:
                self.volumes[dev] = L[0]


    def check_ami(self):
        """Returns true if the ami is available"""
        if self.ami: self.ami.update()
        if self.ami: return self.ami.state == 'available'
        else:        return False


    def check_instance(self):
        """Returns true if there is an instance running"""
        if self.instance: self.instance.update()
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


    @property
    def hostname(self):
        if self.instance: return self.instance.public_dns_name
        else:             return None


    @property
    def ip(self):
        if self.instance: return self.instance.ip_address
        else:             return None


    # Interface
    # ----------------------------------------------------------------

    def launch(self, itype=None, silent=False, dryrun=False):
        """Launches a new instance"""
        itype = itype or self.ec2_itype
        if self.instance == None:
            self.create_instance(itype)


    def terminate(self, silent=False, dryrun=False):
        """Terminates the current instance"""
        if self.STATES.index(self.state) > self.STATES.index('terminated'):
            self.set_state('terminated', silent=silent, dryrun=dryrun)


    def snapshot(self, silent=False, dryrun=False):
        """Creates a snapshot of the running instance"""

        # go online but with detached data
        self.set_state(state='online', silent=silent, dryrun=dryrun)

        ui.print_color("I'm going create a new ami from the running instance:")
        self.print_status()

        cont = ui.ask_question_yesno("Do you want to continue?", default='yes')
        if cont != 'yes': return

        new_ami_name = ui.ask_question_string("Enter the new ami name:")
        description = "%s %s" % (self.name, datetime.date.today().strftime("%Y-%m-%d"))

        ui.print_status(text="Creating %s ami snapshot" % new_ami_name, flag='BUSY')
        self.make_ami_snapshot(name = new_ami_name, desc = description)
        ui.print_status(flag='DONE', nl=True)


    def backup(self, silent=False, dryrun=False):
        """Creates a data backup"""

        # go online but with detached data
        self.set_state(state='online', silent=silent, dryrun=dryrun)

        ui.print_color("I'm going create snapshots for all data volumes")
        self.print_status()

        cont = ui.ask_question_yesno("Do you want to continue?", default='yes')
        if cont != 'yes': return

        for k, dev in self.volumes.items():
            description = "volume %s on %s %s" % (k, self.name, datetime.date.today().strftime("%Y-%m-%d"))
            ui.print_status(text="Creating snapshot for %s" % k, flag='BUSY')
            self.make_data_snapshot(dev = dev, desc = description)
            ui.print_status(flag='DONE', nl=True)


    def attach(self, silent=False, dryrun=False):
        """Attaches volumes"""
        if self.STATES.index(self.state) < self.STATES.index('attached'):
            self.set_state('attached', silent=silent, dryrun=dryrun)


    def detach(self, silent=False, dryrun=False):
        """Deataches volumes"""
        newstate = self.STATES[self.STATES.index('attached') - 1]
        if self.STATES.index(self.state) >= self.STATES.index('attached'):
            self.set_state(newstate, silent=silent, dryrun=dryrun)


    # State transitions
    # ----------------------------------------------------------------
    # TODO:waitings

    def enter_state(self, state):
        if state == 'terminated':
            pass

        elif state == 'offline':
            pass

        elif state == 'online':
            self.start_instance(self.instance.id)

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
            self.stop_instance(self.instance.id)

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
        self.state = 'terminated'
        if self.state == 'terminated'   and self.instance != None: self.state = 'offline'
        if self.state == 'offline'  and \
           self.check_instance() and self.check_ssh():             self.state = 'online'
        if self.state == 'online'   and self.check_volumes():      self.state = 'attached'
        if self.state == 'attached' and self.check_devices():      self.state = 'mounted'

        return self.state

    def get_info(self):
        """Gets a dictionary with host state parameters"""
        ui.print_debug("begin Ec2Host.get_info")

        info = super(Ec2Host, self).get_info()

        if self.ami:
            info['ami_name'] = self.ami.name
            info['ami_id'] = self.ami.id

        if self.instance:
            info['instance'] = self.instance.state
            info['itype'] = self.instance.instance_type
            info['block'] = list(self.instance.block_device_mapping.keys())

        return info


    # backup
    # ------------------------------------------------------

    def make_ami_snapshot(self, name, desc):
        """Creates a snapshot of the running image."""

        self.conn.create_image(instance_id = self.instance.id,
                               name = name,
                               description = desc)

        def _state():
            self.ami.update()
            return self.ami.state

        if not self.wait_for('available', _state, timeout=300):
            raise HostError("Timed out creating ami")


    def make_data_snapshot(self, dev, desc):
        """Creates a snapshot of the data volume."""
        if dev in self.volumes:
            id = self.volumes[dev].id
            self.conn.create_snapshot(volume_id = id,
                                      description = desc)





# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
