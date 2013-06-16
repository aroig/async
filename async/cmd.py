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

import subprocess
import sys
import os
import re


def unison(prf, args=[], force=None, silent=True):
    unison_cmd = 'unison'
    unison_args = [] + args

    with open('/dev/null', 'w') as devnull:
        if silent: out = devnull
        else:      out = None
        subprocess.check_call([unison_cmd] + unison_args + [prf], stderr=out, stdout=out)


def rsync(src, tgt, delete=True, silent=True):
    rsync_cmd = 'rsync'

    if delete:         rsync_args = ['--delete']
    else:              rsync_args = []

    with open('/dev/null', 'w') as devnull:
        if silent: out = devnull
        else:      out = None
        subprocess.check_call([rsync_cmd, '-avq'] + rsync_args + [src + '/', tgt + '/'], stderr=out, stdout=out)


def git(tgtdir, args, silent=False, catchout=False):
    git_cmd = 'git'
    with open('/dev/null', 'w') as devnull:
        if silent: out=devnull
        else:      out=None
        if catchout:
            raw = subprocess.check_output([git_cmd] + args, stderr=out, cwd=tgtdir)
            return raw
        else:
            subprocess.check_call([git_cmd] + args, stderr=out, stdout=out, cwd=tgtdir)


def bash_cmd(tgtdir, cmd, silent=False, catchout=False):
    bash_cmd = 'bash'
    with open('/dev/null', 'w') as devnull:
        if silent: out=devnull
        else:      out=None
        if catchout:
            raw = subprocess.check_output([bash_cmd, '-c', cmd], stderr=out, cwd=tgtdir)
            return raw
        else:
            subprocess.check_call([git_cmd] + args, stderr=out, stdout=out, cwd=tgtdir)


def shell(tgtdir):
    shell_cmd = os.environ.get('$SHELL')
    subprocess.check_call('shell_cmd', cwd=tgtdir)


def ssh(host, args=[]):
    ssh_cmd = 'ssh'
    ssh_args = args
    subprocess.check_call([ssh_cmd] + ssh_args)


def cat_pager(fname):
    pager = os.environ.get('PAGER', 'less')
    subprocess.call('cat "%s" | vimpager' % fname, shell=True)



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
