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
import shlex

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
        else: raise ValueError("Unrecognized boolean value: %s" % val)

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
    if not key in dic: dic[key] = []

    if val:
        dic[key] = []                  # never accumulate args
        for it in shlex.split(val):
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

    elif len(spl) == 1:
        parse_val(spl[0], val, dic)

    elif len(spl) >= 2:
        key = spl[0]
        rest = spl[1]
        if not key in dic: dic[key] = {}

        parse_keyval(rest, val, dic[key], parse_val)



def parse_dict_path(key, val, dic):
    return parse_dict(key, val, dic, parse_path)


def parse_list_path(key, val, dic):
    return parse_list(key, val, dic, parse_path)


def parse_keyval_path(key, val, dic):
    return parse_keyval(key, val, dic, parse_path)


class AsyncConfig(ConfigParser):

    # default values and parsing functions
    FIELDS={
        'host': {
            'dirs'           : ([], parse_list),
            'ignore'         : ([], parse_list_path),
            'symlinks'       : ({}, parse_dict_path),    # key:val. 'key' relative dir is symlinked to 'val'

            'hostname'       : (None, parse_string),
            'user'           : (None, parse_string),
            'mac_address'    : (None, parse_string),

            'ssh_key'        : (None, parse_path),
            'ssh_trust'      : (False, parse_bool),
            'unison_as_rsync': (False, parse_bool),

            'kill_systemd_user' : (False, parse_bool),
            'swapfile'       : (None, parse_path),
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

            'log_cmd'        : ("", parse_path),         # parse as a path to expand shell vars
        },

        'instance': {
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
        },

        'remote': {
            'url'            : (None, parse_string),
            'dead'           : (False, parse_bool),
            'git_hooks\..*'  : ({}, parse_keyval_path),
            'uuid\..*'       : ({}, parse_keyval),
        },

        'directory': {
            'perms'           : ('700', parse_string),   # directory perms
            'type'            : (None, parse_string),    # sync method
            'symlink'         : (None, parse_path),      # the directory is a symlink to this target
            'path'            : (None, parse_path),      # relative path of the dir. None means same as name.
            'path_rename'     : ({},   parse_dict_path), # rename path on specific hosts

            'subdirs'         : ([], parse_list_path),
            'check'           : ([], parse_list),
            'ignore'          : ([], parse_list_path),
            'unison_profile'  : (None, parse_string),
            'unison_args'     : ([], parse_list_args),
            'rsync_args'      : ([], parse_list_args),
            'githooks_dir'    : ("", parse_path),

            'pre_init_hook'          : ([], parse_list_path),  # scripts to run before initialization
            'post_init_hook'         : ([], parse_list_path),  # scripts to run after initialization
            'pre_sync_hook'          : ([], parse_list_path),  # scripts to run before sync
            'post_sync_hook'         : ([], parse_list_path),  # scripts to run after sync
            'pre_sync_remote_hook'   : ([], parse_list_path),  # scripts to run on the remote before sync
            'post_sync_remote_hook'  : ([], parse_list_path),  # scripts to run on the remote after sync
            'check_hook'             : ([], parse_list_path),  # scripts to run before check
        },

        'async': {
            'color'           : (True, parse_bool),     # color UI
            'logfile'         : (None, parse_path),     # logfile
            'pager_cmd'       : ("", parse_path),       # parse as a path to expand shell vars
        },
    }


    def _parse_config(self, conf, fields, defaults):
        dic = {'conf_path': self.path}
        for key, pair in fields.items():
            func   = pair[1]
            initval = pair[0]

            # if key contains a star, it is a regexp. match it!
            if '*' in key:
                Lconf = [k for k, v in conf.items()     if re.match(key, k)]
                Ldef =  [k for k, v in defaults.items() if re.match(key, k)]
            else:
                Lconf = [key]
                Ldef  = [key]
                if not key in dic: dic[key] = initval

            # parse defaults
            for key in Ldef:
                defval = defaults.get(key, None)
                func(key, defval, dic)

            # parse config
            for key in Lconf:
                val = conf.get(key, None)
                func(key, val, dic)

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

        # put objects in a dict for easier acces
        objects = {
            'host': self.host,
            'remote': self.remote,
            'instance': self.instance,
            'directory': self.directory,
        }

        # parse async settings
        self.async = self._parse_config(dict(self.items('async')), AsyncConfig.FIELDS['async'], {})

        # parse sections
        sec_re = re.compile(r'^\s*(.*)\s+([^"]*|"[^"]*")\s*$')
        for sec in self.sections():
            m = sec_re.match(sec)
            if m:
                obj  = m.group(1).strip()
                name = m.group(2).strip('"')
                if not obj in objects.keys():
                    raise AsyncConfigError("Unknown object section '%s'" % obj)

                defaults = dict(self.items('%s_defaults' % obj))
                conf     = dict(self.items(sec))

                objects[obj][name] = self._parse_config(conf, AsyncConfig.FIELDS[obj], defaults)
                objects[obj][name]['name'] = name

        # match instance to ec2 hosts
        for k, val in self.host.items():
            if val['type'] == 'ec2':
                if k in self.instance:
                    val['instance'] = dict(self.instance[k])
                else:
                    raise AsyncConfigError("Unknown instance for host: %s" % k)

        # match remotes to git or annex dirs
        for k, val in self.directory.items():
            if val['type'] == 'annex' or val['type'] == 'git':
                val['git_remotes'] = self.remote

        # attach dirs data to hosts
        for k, val in self.host.items():
            dirs = val['dirs']
            if dirs:
                for k in dirs:
                    if not k in self.directory:
                        raise AsyncConfigError("Unknown directory: %s" % k)

                val['dirs'] = {k: dict(self.directory[k]) for k in dirs}



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
