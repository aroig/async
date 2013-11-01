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


# Parsers
# --------------------------------------------------------------------
# All these parsers accept ket, val, dic. The parse key, val and store it in dic.

# key: key for the entry
# val: value to be parsed. If none, ignore it silently
# old: dictionary containing

def parse_string(key, val, dic):
    if val:
        dic[key] = val.strip()
    return dic.get(key, None)



def parse_bool(key, val, dic):
    if val:
        val = val.strip().lower()
        bval = False

        if val in set(['on', 'true', '1', 'yes']): bval = True
        elif val in set(['off', 'false', '0', 'no']): bval = False
        else: raise ValueError("Unrecognized boolean value: %s" % s)

        dic[key] = bval
    return dic.get(key, None)



def parse_path(key, val, dic):
    if val:
        dic[key] = os.path.expandvars(os.path.expanduser(val.strip()))
    return dic.get(key, None)



def parse_list(key, val, dic, parse_val=parse_string):
    if not key in dic: dic[key] = []

    if val:
        L = val.split(',')

        # do not accumulate with previous values if the list starts with a comma.
        if len(L[0].strip()) == 0: L=L[1:]
        else:                      dic[key] = []

        for it in L:
            v = parse_val('key', it, {})
            if v:
                dic[key].append(v)
    return dic[key]



def parse_list_args(key, val, dic):
    # TODO: handle quoted strings
    if not key in dic: dic[key] = []

    if val:
        dic[key] = []                  # never accumulate args
        for it in val.split(' '):
            dic[key].append(it.strip())
    return dic[key]



def parse_dict(key, val, dic, parse_val=parse_string):
    """ex. dict=A:1,B:2,C:3"""
    if not key in dic: dic[key] = {}

    if val:
        L = val.split(',')

        # do not accumulate with previous values if the list starts with a comma.
        if len(L[0].strip()) == 0: L=L[1:]
        else:                      dic[key] = {}

        for it in L:
            spl = it.strip().split(':', 1)
            if len(spl) == 0:
                continue

            elif len(spl) == 2:
                parse_val(spl[0].strip(), spl[1].strip(), dic[key])

            else:
                raise ValueError("Wrong value for dict field: %s" % key)
    return dic[key]



def parse_keyval(key, val, dic, parse_val=parse_string):
    """ex. uuid:directory = blahblah"""
    ret = {}
    spl = key.strip().split('.', 1)
    if len(spl) == 0:
        return

    elif len(spl) == 2:
        key = spl[0]
        nk = spl[1]

    else:
        raise ValueError("Wrong key for a keyval field: %s" % key)

    if not key in dic: dic[key] = {}
    if val: parse_val(nk, val, dic[key])



def parse_dict_path(key, val, dic):
    return parse_dict(key, val, dic, parse_path)



def parse_list_path(key, val, dic):
    return parse_list(key, val, dic, parse_path)



class AsyncConfig(ConfigParser):

    # default values and parsing functions
    HOST_FIELDS={
        'dirs'           : ([], parse_list),
        'ignore'         : ([], parse_list_path),
        'symlinks'       : ({}, parse_dict_path),    # key:val. 'key' relative dir is symlinked to 'val'

        'hostname'       : (None, parse_string),
        'user'           : (None, parse_string),
        'mac_address'    : (None, parse_string),

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

        'annex_pull'     : ([], parse_list),         # directories where we pull annexed files from remote
        'annex_push'     : ([], parse_list),         # directories where we push annexed files to remote
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

    REMOTE_FIELDS={
        'url'            : (None, parse_string),
        'git_hooks'      : ({}, parse_dict_path),
        'uuid\..*'       : ({}, parse_keyval),
    }

    DIRECTORY_FIELDS={
        'perms'           : ('700', parse_string),   # directory perms
        'type'            : (None, parse_string),    # sync method
        'symlink'         : (None, parse_path),      # the directory is a symlink to this target
        'init_hook'       : (None, parse_path),      # script to run on initialization
        'path'            : (None, parse_path),      # relative path of the dir. None means same as name.
        'path_rename'     : ({},   parse_dict_path), # rename path on specific hosts

        'check'           : ([], parse_list),
        'ignore'          : ([], parse_list_path),
        'unison_profile'  : (None, parse_string),
        'unison_args'     : ([], parse_list_args),
        'rsync_args'      : ([], parse_list_args),

        'pre_sync_hook'   : (None, parse_path),
        'post_sync_hook'  : (None, parse_path),
    }

    ASYNC_FIELDS={
        'color'           : (True, parse_bool),     # color UI
        'logfile'         : (None, parse_path),     # logfile
    }


    def _parse_config(self, sec, fields, defaults):
        dic = {'conf_path': self.path}
        for key, pair in fields.items():
            func   = pair[1]
            initval = pair[0]

            # if key contains a star, it is a regexp. match it!
            if '*' in key:
                L = [k for k, v in self.items(sec) if re.match(key, k)]
            else:
                L = [key]
                if not key in dic: dic[key] = initval

            for key in L:
                if self.has_option(sec, key): val = self.get(sec, key)
                else:                         val = None

                defval = defaults.get(key, None)
                func(key, defval, dic)                 # parse the default value
                func(key, val, dic)                    # parse the value
        return dic


    def __init__(self, cfgdir):
        ConfigParser.__init__(self)
        self.read(glob.glob(os.path.join(cfgdir, '*.conf')))
        self.path = cfgdir

        self.host      = {}
        self.remote    = {}
        self.instance  = {}
        self.directory = {}
        self.async     = {}

        host_defaults = dict(self.items('host_defaults'))
        remote_defaults = dict(self.items('remote_defaults'))
        directory_defaults = dict(self.items('directory_defaults'))
        instance_defaults = dict(self.items('instance_defaults'))

        # parse async settings
        self.async = self._parse_config('async', AsyncConfig.ASYNC_FIELDS, {})

        # parse sections
        sec_re = re.compile(r'^\s*(.*)\s+([^"]*|"[^"]*")\s*$')
        for sec in self.sections():
            m = sec_re.match(sec)
            if m:
                obj  = m.group(1).strip()
                name = m.group(2).strip('"')

                if obj == 'instance':
                    self.instance[name] = self._parse_config(sec, AsyncConfig.INSTANCE_FIELDS, instance_defaults)
                    self.instance[name]['name'] = name

                elif obj == 'directory':
                    self.directory[name] = self._parse_config(sec, AsyncConfig.DIRECTORY_FIELDS, directory_defaults)
                    self.directory[name]['name'] = name

                elif obj == 'remote':
                    self.remote[name] = self._parse_config(sec, AsyncConfig.REMOTE_FIELDS, remote_defaults)
                    self.remote[name]['name'] = name

                elif obj == 'host':
                    self.host[name] = self._parse_config(sec, AsyncConfig.HOST_FIELDS, host_defaults)
                    self.host[name]['name'] = name

                else:
                    continue


        # match instance to ec2 hosts
        for k, val in self.host.items():
            if val['type'] == 'ec2':
                if k in self.instance:
                    val['instance'] = dict(self.instance[k])
                else:
                    raise AsyncConfigError("Unknown instance for host: %s" % k)


        # match remotes to annex dirs
        for k, val in self.directory.items():
            if val['type'] == 'annex':
                val['annex_remotes'] = self.remote


        # attach dirs data to hosts
        for k, val in self.host.items():
            dirs = val['dirs']
            if dirs:
                for k in dirs:
                    if not k in self.directory:
                        raise AsyncConfigError("Unknown directory: %s" % k)

                val['dirs'] = {k: dict(self.directory[k]) for k in dirs}



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
