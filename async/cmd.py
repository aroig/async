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

from threading  import Thread
from Queue import Queue, Empty

import async.archui as ui


def print_rsync_line(line):
    ui.write_color("%s" % line)


def print_unison_line(line):
    ui.write_color("%s" % line)


def print_annex_line(line):
    ui.write_color("%s" % line)


class StdoutWriter(Thread):
    def __init__(self, stream, char_callback, line_callback):
        super(StdoutWriter, self).__init__()
        self.stream = stream
        self.char_callback = char_callback
        self.line_callback = line_callback
        self.force_newline = False
        self.daemon = True

    def run(self):
        line0='  '

        line = line0
        b = 'a'
        while len(b) > 0:
            b = self.stream.read(1)

            # when forcing a newline, just reset line without calling callback. We can't
            # guarantee an other '\n' (from stdin for example) messes up with the rewriting.
            if self.force_newline:
                line = line0
                self.force_newline = False
                if self.char_callback: self.char_callback(line)

            # reset line and call callback to rewrite the line. we know there is no extra '\n'
            # in the tty.
            if b == '\n' or b == '\r':
                line = line + b
                if self.char_callback: self.char_callback('\r')
                if self.line_callback: self.line_callback(line)
                line = line0
                if self.char_callback: self.char_callback(line)

            else:
                line = line + b
                if self.char_callback: self.char_callback(b)

        self.stream.close()


class StdinReader(Thread):
    def __init__(self, stream, char_callback, line_callback):
        super(StdinReader, self).__init__()
        self.stream = stream
        self.char_callback = char_callback
        self.line_callback = line_callback
        self.daemon = True

    def run(self):
        line = ''
        b = 'a'
        while len(b) > 0:
            b = self.stream.read(1)
            line = line + b
            if b == '\n':
                if self.line_callback: self.line_callback(line)
                line = ''
        self.stream.close()


def run_stream(args, callback=None, cwd=None):
    """Runs a process, streaming its stdout through a callback function, but still accepting
       interactive input"""

    # process and queue
    proc = subprocess.Popen(args, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, stdin=subprocess.PIPE, cwd=cwd)
    force_newline = False


    def char_to_sys_stdout(b):
        sys.stdout.write(b)
        sys.stdout.flush()

    stdout_writer = StdoutWriter(stream=proc.stdout, char_callback=char_to_sys_stdout, line_callback=callback)


    def line_to_proc_stdin(line):
        proc.stdin.write(line)
        proc.stdin.flush()
        stdout_writer.force_newline = True

    stdin_reader = StdinReader(stream=sys.stdin, char_callback=None, line_callback=line_to_proc_stdin)

    stdout_writer.start()
    stdin_reader.start()

    # wait until process finishes
    ret = proc.wait()

    if ret:
        raise subprocess.CalledProcessError(ret, ' '.join(args))

    return 0


def unison(args=[], silent=True):
    unison_cmd = 'unison'
    unison_args = [] + args

    if silent: func = None
    else:      func = print_unison_line

    run_stream([unison_cmd] + unison_args, callback=func)


def rsync(src, tgt, args=[], silent=True):
    rsync_cmd = 'rsync'
    rsync_args = args

    if src[-1] != '/': A = '%s/' % src
    else:              A = src

    if tgt[-1] != '/': B = '%s/' % tgt
    else:              B = tgt

    if silent: func = None
    else:      func = print_rsync_line

    run_stream([rsync_cmd] + rsync_args + [A, B], callback=func)


def annex(tgtdir, args=[], silent=True):
    git_cmd = 'git'
    git_args = ['annex'] + args

    if silent: func = None
    else:      func = print_annex_line

    run_stream([git_cmd] + git_args, callback=func, cwd=tgtdir)


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
            subprocess.check_call([bash_cmd, '-c', cmd], stderr=out, stdout=out, cwd=tgtdir)


def shell(tgtdir):
    shell_cmd = os.environ.get('SHELL')
    subprocess.check_call([shell_cmd], cwd=tgtdir)


def ssh(host, args=[]):
    ssh_cmd = 'ssh'
    ssh_args = args
    subprocess.check_call([ssh_cmd] + ssh_args + [host])


def mount(path):
    subprocess.check_call(['mount', path])


def umount(path):
    subprocess.check_call(['umount', path])


def cat_pager(fname):
    pager = os.environ.get('PAGER', 'less')
    subprocess.call('cat "%s" | %s' % (fname, pager), shell=True)



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
