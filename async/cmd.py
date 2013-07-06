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
import inspect
import ctypes
import sys
import os
import re

from threading  import Thread, Event
from Queue import Queue, Empty

import async.archui as ui


def print_rsync_line(line):
    print("")
#    ui.write_color("\r%s" % line)


def print_unison_line(line):
    print("")
#    ui.write_color("\r%s" % line)


def print_annex_line(line):
    print("")
#    ui.write_color("\r%s" % line)


class StreamWriter(Thread):
    """Gets characters from stream. Calls char_callback one character at a time
       and line_callback one line at a time"""

    def __init__(self, stream, char_callback, line_callback, prefix=''):
        super(StreamWriter, self).__init__()
        self.stream = stream
        self.char_callback = char_callback
        self.line_callback = line_callback
        self.prefix = prefix
        self._force_newline = Event()
        self.daemon = True


    def force_newline(self):
        """Forces a newline, for example after user input"""
        self._force_newline.set()


    def run(self):
        line = self.prefix
        b = 'a'
        while len(b) > 0:
            b = self.stream.read(1)

            # when forcing a newline, just reset line without calling callback. We can't
            # guarantee an other '\n' (from stdin for example) messes up with the rewriting.
            if self._force_newline.is_set():
                line = self.prefix
                self._force_newline.clear()
                if self.char_callback: self.char_callback(line)

            line = line + b

            # call line_callback to rewrite line.
            if b == '\n':
                if self.line_callback:
                    self.line_callback(line)
                line = self.prefix
                if self.char_callback and len(line) > 0:
                    self.char_callback(line)

            # do not call line_callback when already rewriting a line
            elif b == '\r':
                if self.char_callback: self.char_callback('\r')
                line = self.prefix
                if self.char_callback and len(line) > 0:
                    self.char_callback(line)

            else:
                if self.char_callback: self.char_callback(b)

        self.stream.close()



def run_stream(args, callback=None, cwd=None):
    """Runs a process, streaming its stdout through a callback function, but still accepting
       interactive input"""

    # NOTE: if I redirect stderr to stdout here, unison eventually fails because stderr blocks.

    # TODO: I'd like to monitor stdin and call stdout_writer.force_newline() after each input.
    # the p problem is that I don't know how to releiably stop listening to stdin after proc ends.
    proc = subprocess.Popen(args, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                            bufsize=-1, cwd=cwd)

    def char_to_sys_stdout(b):
        sys.stdout.write(b)
        sys.stdout.flush()

    stdout_writer = StreamWriter(stream=proc.stdout, char_callback=char_to_sys_stdout,
                                 line_callback=callback, prefix='  ')

#    stderr_writer = StreamWriter(stream=proc.stderr, char_callback=char_to_sys_stdout,
#                                 line_callback=callback, prefix='  ')


#    def line_to_proc_stdin(line):
#        proc.stdin.write(line)
#        proc.stdin.flush()
#        stdout_writer.force_newline()

#    stdin_writer = StreamWriter(stream=sys.stdin, char_callback=None,
#                                 line_callback=line_to_proc_stdin, prefix='')

    stdout_writer.start()
 #   stderr_writer.start()
 #   stdin_writer.start()

    # wait until process finishes
    ret = proc.wait()

    stdout_writer.join()

    if ret:
        raise subprocess.CalledProcessError(ret, ' '.join(args))

    return 0


def unison(args=[], silent=True):
    unison_cmd = 'unison'
    unison_args = [] + args

#    if silent: func = None
#    else:      func = print_unison_line
#
#    run_stream([unison_cmd] + unison_args, callback=func)

    with open('/dev/null', 'w') as devnull:
        if silent: out=devnull
        else:      out=None

        subprocess.check_call([unison_cmd] + unison_args, stderr=out, stdout=out)


def rsync(src, tgt, args=[], silent=True):
    rsync_cmd = 'rsync'
    rsync_args = args

    if src[-1] != '/': A = '%s/' % src
    else:              A = src

    if tgt[-1] != '/': B = '%s/' % tgt
    else:              B = tgt

    with open('/dev/null', 'w') as devnull:
        if silent: out=devnull
        else:      out=None

        subprocess.check_call([rsync_cmd] + rsync_args + [A, B], stderr=out, stdout=out)


def annex(tgtdir, args=[], silent=True):
    git_cmd = 'git'
    git_args = ['annex'] + args

    with open('/dev/null', 'w') as devnull:
        if silent: out=devnull
        else:      out=None

        subprocess.check_call([git_cmd] + git_args, stderr=out, stdout=out, cwd=tgtdir)


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


def wake_on_lan(mac):
    subprocess.check_call(['wol', mac])


def ping(host, timeout=10, num=1):
    try:
        raw = subprocess.check_output(["ping", "-q", "-c", str(num), "-w", str(timeout), host])

    except subprocess.CalledProcessError:
        return (None, None, None, None)

    m = re.search("min/avg/max/mdev = (\d+.\d+)/(\d+.\d+)/(\d+.\d+)/(\d+.\d+)", raw)
    if m:
        return (float(t) / 1000 for t in m.groups())
    else:
        return (None, None, None, None)


def cat_pager(fname):
    pager = os.environ.get('PAGER', 'less')
    subprocess.call('cat "%s" | %s' % (fname, pager), shell=True)



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
