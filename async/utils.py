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
    if num >= 1.0:
        for s in super_symbols[0:]:
            symbol = s
            if scale*1000.0 > num: break
            scale = scale*1000.0

    else:
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
