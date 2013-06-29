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

import os
import re
import glob

from ConfigParser import ConfigParser

class AsyncConfigError(Exception):
    def __init__(self, msg=None):
        super(AsyncConfigError, self).__init__(msg)


def parse_string(s):
    if s == None: return None
    return s.strip()


def parse_bool(s):
    if s == None: return None
    val = s.strip().lower()
    if val in set(['on', 'true', '1', 'yes']): return True
    elif val in set(['off', 'false', '0', 'no']): return False
    else: raise ValueError("Unrecognized boolean value: %s" % s)


def parse_path(s):
    if s == None: return None
    return os.path.expandvars(os.path.expanduser(s.strip()))


def parse_list(s, parse_val=parse_string):
    if s == None: return []
    return [parse_val(it) for it in s.split(',')]


def parse_list_args(s):
    # TODO: handle quoted strings
    if s == None: return []
    return [it.strip() for it in s.split(' ')]


def parse_dict(s, parse_val=parse_string):
    if s == None: return {}
    dic = {}

    for it in s.split(','):
        spl = it.strip().split(':')
        if len(spl) > 2:
            raise AsyncConfigError("Can't parse keyval string: %s" % s)
            break
        elif len(spl) == 0:
            continue

        if len(spl) == 2:  val=spl[1].strip()
        else:              val=spl[0].strip()

        if parse_val:      val = parse_val(val)

        if len(spl) == 2:  key=spl[0].strip()
        else:              key=val

        dic[key] = val

    return dic


def parse_dict_path(s):
    return parse_dict(s, parse_path)

def parse_list_path(s):
    return parse_list(s, parse_path)



class AsyncConfig(ConfigParser):
    instance_re = re.compile(r'^\s*instance\s+([^"]*|"[^"]*")\s*$')
    remote_re = re.compile(r'^\s*remote\s+([^"]*|"[^"]*")\s*$')
    host_re = re.compile(r'^\s*host\s+([^"]*|"[^"]*")\s*$')
    directory_re = re.compile(r'^\s*directory\s+([^"]*|"[^"]*")\s*$')


    # default values and parsing functions

    HOST_FIELDS={
        'dirs'           : ([], parse_list),
        'nosync'         : ([], parse_list),
        'symlinks'       : ({}, parse_dict_path),    # key:val. 'key' relative dir is symlinked to 'val'

        'hostname'       : (None, parse_string),
        'user'           : (None, parse_string),

        'ssh_key'        : (None, parse_path),
        'ssh_trust'      : (False, parse_bool),
        'unison_as_rsync': (False, parse_bool),

        'mounts'         : ({}, parse_dict),
        'luks'           : ({}, parse_dict),
        'ecryptfs'       : ({}, parse_dict),
        'vol_keys'       : (None, parse_path),

        'path'           : (None, parse_path),
        'check'          : ([], parse_list),
        'type'           : (None, parse_string),
        'instance'       : (None, parse_string),
}

    INSTANCE_FIELDS={
        'ec2_ami'        : (None, parse_string),
        'ec2_owner'      : (None, parse_string),
        'ec2_region'     : (None, parse_string),
        'ec2_itype'      : (None, parse_string),

        'ec2_keypair'    : (None, parse_string),
        'ec2_security_group' : (None, parse_string),

        'aws_keys'       : (None, parse_path),
        'volumes'        : ({}, parse_dict),

        'zone'           : (None, parse_string),
        'user'           : (None, parse_string),
}

    REMOTE_FIELDS={}

    DIRECTORY_FIELDS={
        'perms'           : ('700', parse_string),   # directory perms
        'type'            : (None, parse_string),    # sync method
        'symlink'         : (None, parse_path),      # the directory is a symlink to this target
        'setup_hool'      : (None, parse_path),      # script to run on setup
        'path'            : (None, parse_path),      # relative path of the dir. None means same as name.
        'check'           : ([], parse_list),
        'ignore'          : ([], parse_list_path),
        'unison_profile'  : (None, parse_string),
        'unison_args'     : ([], parse_list_args),
        'rsync_args'      : ([], parse_list_args),
        'annex_get'       : (True, parse_bool),

        'hooks_path'      : (None, parse_path),
        'pre_sync_hook'   : (None, parse_path),
        'post_sync_hook'  : (None, parse_path),
}

    ASYNC_FIELDS={
        'color'           : (True, parse_bool),     # color UI
        'logfile'         : (None, parse_path),     # logfile
    }


    def _parse_config(self, sec, fields, defaults):
        dic = {}
        for k, pair in fields.items():
            func = pair[1]

            if self.has_option(sec, k): val = self.get(sec, k)
            else:                       val = defaults.get(k, None)

            if val:  dic[k] = func(val)
            else:    dic[k] = pair[0]

        return dic


    def __init__(self, cfgdir):
        ConfigParser.__init__(self)
        self.read(glob.glob(os.path.join(cfgdir, '*.conf')))

        self.host = {}
        self.remote = {}
        self.instance = {}
        self.directory = {}
        self.async = {}

        host_defaults = dict(self.items('host_defaults'))
        remote_defaults = dict(self.items('remote_defaults'))
        directory_defaults = dict(self.items('directory_defaults'))
        instance_defaults = dict(self.items('instance_defaults'))

        # parse async settings
        self.async = self._parse_config('async', AsyncConfig.ASYNC_FIELDS, {})

        # parse sections
        for sec in self.sections():
            m = self.instance_re.match(sec)
            if m:
                name = m.group(1).strip('"')
                self.instance[name] = self._parse_config(sec, AsyncConfig.INSTANCE_FIELDS, instance_defaults)
                self.instance[name]['name'] = name
                continue

            m = self.directory_re.match(sec)
            if m:
                name = m.group(1).strip('"')
                self.directory[name] = self._parse_config(sec, AsyncConfig.DIRECTORY_FIELDS, directory_defaults)
                self.directory[name]['name'] = name
                continue

            m = self.remote_re.match(sec)
            if m:
                name = m.group(1).strip('"')
                self.remote[name] = self._parse_config(sec, AsyncConfig.REMOTE_FIELDS, remote_defaults)
                self.remote[name]['name'] = name
                continue

            m = self.host_re.match(sec)
            if m:
                name = m.group(1).strip('"')
                self.host[name] = self._parse_config(sec, AsyncConfig.HOST_FIELDS, host_defaults)
                self.host[name]['name'] = name
                continue


        # match instance to ec2 hosts
        for k, val in self.host.items():
            if val['type'] == 'ec2':
                if k in self.instance:
                    val['instance'] = self.instance[k]
                else:
                    raise AsyncConfigError("Unknown instance for host: %s" % k)


        # attach dirs data to hosts
        for k, val in self.host.items():
            dirs = val['dirs']
            if dirs:
                for k in dirs:
                    if not k in self.directory:
                        raise AsyncConfigError("Unknown directory: %s" % k)

                val['dirs'] = {k: self.directory[k] for k in dirs}



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
