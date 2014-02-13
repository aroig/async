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

from async.hosts.ssh import SshHost, SshError
from async.hosts.base import HostError

from datetime import datetime, date
from boto import ec2
from boto.exception import EC2ResponseError

import async.archui as ui
import async.cmd as cmd
import async.utils as utils


class Ec2Error(Exception):
    def __init__(self, msg=None):
        super(Ec2Error, self).__init__(msg)


class Ec2Host(SshHost):
    """An ec2 instance"""
    # ordered list of states. terminate does not belong here as it destroys the instance.
    STATES = ['terminated', 'offline', 'running', 'online', 'attached', 'mounted']

    def __init__(self, conf):
        ui.print_debug("begin Ec2Host.__init__")

        # base config
        super(Ec2Host, self).__init__(conf)

        # ec2 instance
        self.ec2_ami = conf['instance']['ec2_ami']
        self.ec2_itype = conf['instance']['ec2_itype']
        self.ec2_owner = conf['instance']['ec2_owner']
        self.ec2_zone  = conf['instance']['zone']

        self.ec2_keypair        = conf['instance']['ec2_keypair']
        self.ec2_security_group = conf['instance']['ec2_security_group']

        self.ec2_region = conf['instance']['ec2_region']
        self.aws_keys = utils.read_keys(conf['instance']['aws_keys'])

        self.ec2_vol = conf['instance']['volumes']

        self.conn = None
        self.volumes = {}
        self.ami = None
        self.instance = None


    def __del__(self):
        self.ssh_disconnect()
        self.aws_disconnect()



    # Utilities
    # ----------------------------------------------------------------

    def detach_volume(self, vol):
        try:
            vol.update()
            if vol.attachment_state() != 'detached':
                vol.detach()

        except EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            vol.update()
            return vol.attachment_state()

        if not self.wait_for(None, _state):
            raise HostError("Timed out detaching")



    def attach_volume(self, vol, inst, dev):
        try:
            vol.update()
            if vol.attachment_state() != 'attached':
                vol.attach(inst, dev)

        except EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            vol.update()
            return vol.attachment_state()

        if not self.wait_for('attached', _state):
            raise HostError("Timed out attaching")


    def start_instance(self, id):
        try:
            self.conn.start_instances([id])
        except EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            self.instance.update()
            return self.instance.state

        if not self.wait_for('running', _state):
            raise HostError("Timed out starting instance")


    def stop_instance(self, id):
        try:
            self.conn.stop_instances([id])
        except EC2ResponseError as err:
            raise HostError(str(err))

        def _state():
            self.instance.update()
            return self.instance.state

        if not self.wait_for('stopped', _state):
            raise HostError("Timed out stopping instance")


    def create_instance(self, ami_id, itype):
        """Creates a new instance"""
        try:
            res = self.conn.run_instances(min_count = 1, max_count = 1,
                                          image_id = ami_id,
                                          key_name = self.ec2_keypair,
                                          security_groups = [self.ec2_security_group],
                                          instance_type = itype,
                                          placement = self.ec2_zone)

        except EC2ResponseError as err:
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


    def aws_connect(self):
        if self.conn == None:
            self.conn = ec2.connect_to_region(region_name = self.ec2_region,
                                              aws_access_key_id = self.aws_keys['access_key_id'],
                                              aws_secret_access_key = self.aws_keys['secret_access_key'])

            self.load_volumes()
            self.load_ami()
            self.load_instance()

        if self.conn == None:
            raise Ec2Error("Could not establish a connection with aws.")


    def aws_disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None



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


    def load_volumes(self):
        for dev, vol in self.ec2_vol.items():
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
        if self.ami:
            ui.print_debug("check_ami. ami: %s, state: %s" % (self.ami.id, self.ami.state))
            return self.ami.state == 'available'
        else:
            return False


    def check_instance(self):
        """Returns true if there is an instance running"""
        if self.instance: self.instance.update()
        if self.instance:
            ui.print_debug("check_instance. instance: %s, state: %s" % (self.instance.id, self.instance.state))
            return self.instance.state == 'running'
        else:
            return False


    def check_volumes(self):
        """Returns true if all the volumes are attached"""
        attached = True
        for dev, vol in self.volumes.items():
            vol.update()
            state = vol.attachment_state()
            ui.print_debug("check_volumes. vol: %s, state: %s" % (dev, state))
            if not state == 'attached':
                attached = False
        return attached


    def check_aws(self):
        self.aws_connect()
        return self.instance != None



    # Interface
    # ----------------------------------------------------------------

    def connect(self):
        """Establish a connection to the server"""
        self.aws_connect()
        self.ssh_connect(alt_hostname=self.hostname)


    def launch(self, itype=None, silent=False, dryrun=False):
        """Launches a new instance"""
        itype = itype or self.ec2_itype
        ret = False
        self.connect()

        try:
            if self.instance == None:

                def func():
                    self.create_instance(ami_id=self.ami.id, itype=itype)

                self.run_with_message(func=func,
                                      msg="Launching instance of %s (%s, %s)" % (self.name, self.ami.id, itype),
                                      silent=silent,
                                      dryrun=dryrun)
                ret = True

            else:
                ui.print_error("There is already a running instance.")
                ret = False

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def start(self, silent=False, dryrun=False):
        """Starts the host if not running and attach."""
        st = 'attached'
        ret = True
        if self.state == None: self.get_state()

        try:
            if self.STATES.index(self.state) < self.STATES.index('attached'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def terminate(self, silent=False, dryrun=False):
        """Terminates the current instance"""
        st = 'terminated'
        ret = True
        if self.state == None: self.get_state()

        try:
            if self.STATES.index(self.state) > self.STATES.index('terminated'):
                ret =  self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def attach(self, silent=False, dryrun=False):
        """Attaches volumes"""
        st = 'attached'
        ret = True
        if self.state == None: self.get_state()

        try:
            if self.STATES.index(self.state) < self.STATES.index('attached'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def detach(self, silent=False, dryrun=False):
        """Deataches volumes"""
        st = self.STATES[self.STATES.index('attached') - 1]
        ret = True
        if self.state == None: self.get_state()

        try:
            if self.STATES.index(self.state) >= self.STATES.index('attached'):
                ret = self.set_state(st, silent=silent, dryrun=dryrun) == st

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def snapshot(self, silent=False, dryrun=False):
        """Creates a snapshot of the running instance"""
        ret = False
        if self.state == None: self.get_state()

        try:
            # go to online state, with detached data
            self.set_state(state='online', silent=silent, dryrun=dryrun)

            ui.print_status("I'm going create a new ami from the running instance")
            self.print_status()

            cont = ui.ask_question_yesno("Do you want to continue?", default='yes')
            if cont == 'yes':
                new_ami_name = ui.ask_question_string("Enter the new ami name:")
                description = "%s %s" % (self.name, date.today().strftime("%Y-%m-%d"))
                def func():
                    self.make_ami_snapshot(name = new_ami_name, desc = description)

                self.run_with_message(func=func,
                                      msg="Creating %s ami snapshot" % new_ami_name,
                                      silent=silent,
                                      dryrun=dryrun)
                ret = True

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def backup(self, silent=False, dryrun=False):
        """Creates a data backup"""
        ret = False
        if self.state == None: self.get_state()

        try:
            # go to online state with detached data
            self.set_state(state='online', silent=silent, dryrun=dryrun)

            ui.print_status("I'm going create snapshots for all data volumes")
            self.print_status()

            cont = ui.ask_question_yesno("Do you want to continue?", default='yes')
            if cont == 'yes':
                for k, dev in self.volumes.items():
                    description = "volume %s on %s %s" % (k, self.name, date.today().strftime("%Y-%m-%d"))
                    def func():
                        self.make_data_snapshot(dev = dev, desc = description)

                    self.run_with_message(func=func,
                                          msg="Creating volume backup for %s" % k,
                                          silent=silent,
                                          dryrun=dryrun)
                    ret = True

        except HostError as err:
            ui.print_error(str(err))
            ret = False

        return ret


    def ping(self):
        """Pings the host and prints the delay"""
        self.connect()
        super(Ec2Host, self).ping()


    def print_log(self, silent=False, dryrun=False, opts=None):
        """Prints host logs"""
        if opts and opts.boot:
            self.connect()
            if not dryrun:
                cout = self.instance.get_console_output()
                print(cout.output)

        else:
            super(Ec2Host, self).print_log(silent=silent, dryrun=dryrun, opts=opts)



    # State transitions
    # ----------------------------------------------------------------

    def enter_state(self, state):
        if self.state == 'terminated':
            raise HostError("Instance terminated. please launch an instance")

        if state == 'terminated':
            pass

        elif state == 'offline':
            self.aws_connect()

        elif state == 'running':
            self.start_instance(self.instance.id)

        elif state == 'online':
            self.ssh_connect(alt_hostname=self.hostname)

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

        elif state == 'running':
            self.stop_instance(self.instance.id)

        elif state == 'online':
            pass

        elif state == 'attached':
            for dev, vol in self.volumes.items():
                self.detach_volume(vol)

        elif state == 'mounted':
            self.umount_devices()

        else:
            raise HostError("Unknown state %s" % state)



    # Implementation
    # ----------------------------------------------------------------

    @property
    def hostname(self):
        if self.instance: return self.instance.public_dns_name
        else:             return None


    @property
    def ip(self):
        if self.instance: return self.instance.ip_address
        else:             return None


    def get_state(self):
        """Queries the state of the host"""
        self.state = 'terminated'
        if self.check_aws():                                       self.state = 'offline'
        if self.state == 'offline'  and self.check_instance():     self.state = 'running'
        if self.state == 'running'  and self.check_ssh():          self.state = 'online'
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


            info['block'] = {}
            for k in self.instance.block_device_mapping.keys():
                k = str(k)
                if k in self.volumes:
                    state = self.volumes[k].attachment_state()
                elif k == str(self.instance.root_device_name):
                    state = 'root'
                else:
                    state = 'unknown'

                info['block'][k] = state

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
