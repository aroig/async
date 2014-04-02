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
import json

from datetime import datetime
import dateutil.parser

import shlex
import sys

if sys.version_info[0] < 3:
    def shquote(s):
        return "'" + s.replace("'", "'\"'\"'") + "'"
else:
    shquote = shlex.quote


def number2human(num, fmt="%(value)3.2f %(symbol)s", suffix=''):
    """
    >>> number2human(10000)
    '9 K'
    >>> number2human(100001221)
    '95 M'
    """
    super_symbols = ('', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    sub_symbols   = ('', 'm', 'u', 'n', 'p', 'f', 'a', 'z', 'y')

    scale = 1.0
    symbol = ''
    if abs(num) >= 1.0:
        for s in super_symbols[0:]:
            symbol = s
            if scale*1000.0 > num: break
            scale = scale*1000.0

    elif abs(num) >= 1e-24:
        for s in sub_symbols[0:]:
            symbol = s
            if scale <= num: break
            scale = scale/1000.0

    value = float(num) / scale
    return (fmt % dict(value=value, symbol=symbol+suffix)).strip()



def read_keys(path):
    """Reads keys from a file. each line is formatted as id = key"""
    keys = {}
    with open(path, 'r') as fd:
        for line in fd:
            m = re.match(r'^(.*)=(.*)$', line)
            if m: keys[m.group(1).strip()] = m.group(2).strip()

    return keys



def save_lastsync(host, path, rname, success):
    """Save sync success state"""
    lsfile = os.path.join(path, host.asynclast_file)
    now = datetime.today().isoformat()
    data = json.dumps({'remote': rname,
                       'timestamp': now,
                       'success': success})
    host.run_cmd('echo %s > %s' % (shquote(data), shquote(lsfile)))



def read_lastsync(host, path):
    lsfile = os.path.join(path, host.asynclast_file)
    raw = host.run_cmd('[ -f %s ] && cat %s || true' % (shquote(lsfile), shquote(lsfile)),
                       catchout=True).strip()
    try:
        ls = json.loads(raw)
        return {'remote': ls['remote'],
                'timestamp': dateutil.parser.parse(ls['timestamp']),
                'success': ls['success']}

    except:
        return {'remote': None,
                'timestamp': None,
                'success': None}
