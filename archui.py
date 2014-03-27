#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# archui - a very simple arch linux style UI library
# Copyright 2012 Abdó Roig-Maranges <abdo.roig@gmail.com>
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

import sys
import re
import os
from collections import OrderedDict

_cc = OrderedDict()

# Load curses
try:
    import curses
    curses.setupterm()

    _numcolors = curses.tigetnum('colors')
    _setfg = curses.tigetstr('setaf')
    _setbg = curses.tigetstr('setab')
    _bold  = curses.tigetstr('bold')
    _reset = curses.tigetstr('sgr0')

except:
    _numcolors = 2


# Encode in ascii
if sys.version_info[0] <= 2:
    def _str(n):
        return str(n)
else:
    def _str(n):
        return str(n, encoding='ascii')

# want input to return a string. On python2 this is raw_input!
if sys.version_info[0] <= 2:
    input = raw_input

if _numcolors >= 16:
    for i, k in enumerate("krgybmcw"):
        _cc[k.upper()] = _str(_reset + curses.tparm(_setfg, i))     # dark
        _cc[k]         = _str(_reset + curses.tparm(_setfg, i + 8)) # light
        _cc['*'+k]     = _str(_bold + curses.tparm(_setfg, i))      # bold
        _cc['t']       = _str(_reset)
        _cc['#']       = "#"

elif _numcolors >= 8:
    for i, k in enumerate("krgybmcw"):
        _cc[k.upper()] = _str(_reset + curses.tparm(_setfg, i)) # dark
        _cc[k]         = _str(_bold + curses.tparm(_setfg, i))  # bold
        _cc['*'+k]     = _str(_bold + curses.tparm(_setfg, i))  # bold
        _cc['t']       = _str(_reset)
        _cc['#']       = "#"

else:
    for i, k in enumerate("krgybmcw"):
        _cc[k.upper()] = ""
        _cc[k]         = ""
        _cc['*'+k]     = ""
        _cc['t']       = "\033[0m"
        _cc['#']       = "#"


fc = {'done'  : '#G',
      'fail'  : '#R',
      'busy'  : '#Y',
      'start' : '#G',
      'stop'  : '#G'
      }


# Internal state
_mc = '#*b'           # main color
_maxwidth = 80        # max text width

_loglevel   = 4       # the log level
_debug      = 0       # debug flag
_use_color  = True    # use colors flag
_last_status = ""     # remember text of last print_status

_logger = None
_isatty = sys.stdout.isatty()

def start_logging(logfile, level=4):
    path = os.path.expandvars(os.path.expanduser(logfile))
    try:
        os.makedirs(os.path.dirname(path))
    except:
        pass

    try:
        fd = open(logfile, 'w')

        global _logger
        _logger = fd

        global _loglevel
        _loglevel = level

    except:
        print_error("Can't setup logging to %s" % logfile)

def stop_logging():
    global _logger
    if _logger != None: _logger.close()
    _logger = None

def set_loglevel(level):
    """logging level: 0 none, 1 errors, 2 warnings, 3 info, 4 messages, 5 debug"""
    global _loglevel
    _loglevel = level

def set_debug(dbg):
    global _debug
    _debug = dbg

def use_color(cl):
    global _use_color
    _use_color = cl

def set_main_color(c):
    global _mc
    _mc = c

def get_terminal_size():
    env = os.environ
    def ioctl_GWINSZ(fd):
        try:
            import fcntl, termios, struct, os
            cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,
                                                 '1234'))
        except:
            return None
        return cr

    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass

    if not cr:
        cr = (None, None)

    if cr[0]: row = int(cr[0])
    else:     row = None

    if cr[1]: col = int(cr[1])
    else:     col = None

    return (row, col)

def get_line_width():
    row, col = get_terminal_size()
    if col: return col
    else:   return _maxwidth


def strip_color(s):
    return re.sub(r'\x1b[^m]*m|\x1b[^B]*B', '', s)


def color(s, use_color=None):
    global _isatty
    global _use_color
    if use_color == None:
        use_color = _use_color and _isatty

    ret = s + '#t'
    if use_color:
        for k in _cc: ret = ret.replace('#'+k, _cc[k])
    else:
        for k in _cc: ret = ret.replace('#'+k, '')

    return ret


def print_color(text, file=sys.stdout):
    write_color(text + '\n', file)

def write_color(text, file=sys.stdout, loglevel=4, debug=0):
    global _debug
    if debug <= _debug:
        file.write('%s' % color(text))
        file.flush()
    write_log(text, level=loglevel)

def print_log(text, level=3):
    write_log(txt + '\n', level=level)

def write_log(text, level=3):
    global _logger, _loglevel
    if _logger != None and level <= _loglevel:
        _logger.write('%s' % color(text, use_color=False))



def print_debug(text, level=1):
    write_color("#*gdebug:#t %s\n" % text, file=sys.stderr, loglevel=5, debug=level)

def print_message(text):
    write_color(" %s\n" % text, file=sys.stdout, loglevel=4)

def print_error(text):
    write_color('#*rerror: #w%s\n' % text, file=sys.stderr, loglevel=1)

def print_warning(text):
    write_color('#*ywarning: #w%s\n' % text, file=sys.stderr, loglevel=2)

def print_info(text):
    write_color('#*binfo: #w%s\n' % text, file=sys.stderr, loglevel=3)



def print_item(text):
    write_color('%s * #*w%s\n' % (_mc, text), file=sys.stdout, loglevel=3)

def print_heading(text):
    write_color('%s > #*w%s\n' % (_mc, text), file=sys.stdout, loglevel=3)

def print_enum(i, n, text):
    write_color('%s(%d/%d) #t%s\n' % (_mc, i, n, text), file=sys.stdout, loglevel=3)


# TODO: get rid of nl where I use it
def print_status(text=None, flag=None, nl=None):
    global _isatty, _last_status

    # message part widths
    fwidth = 10
    width = min(get_line_width(), _maxwidth)
    if flag: mwidth = width - fwidth
    else:    mwidth = width

    # handle existing newline in text
    if nl == None:
        if re.match("^.*\n\s*$", text, re.MULTILINE): nl = True
        else:                                         nl = False
    if text: text = text.strip()

    # if changing status, use cached message
    if text == None: text = _last_status
    else:            _last_status = text

    # format string for the message
    if _isatty:
        if flag: fmt = '\r%s:: #*w{0:<%s}{1:>%s}' % (_mc, mwidth, fwidth)
        else:    fmt = '\r%s:: #*w{0:<%s}' % (_mc, mwidth)

    else:
        if flag: fmt = '%s:: #*w{0} {1}' % (_mc)
        else:    fmt = '%s:: #*w{0}'    % (_mc)
        nl = True

    if nl: fmt = fmt + '\n'
    else:  fmt = fmt + '\r'

    # write the message
    if flag:
        if flag.lower() in fc: col = fc[flag.lower()]
        else:                  col = '#W'
        sta = '%s[%s%s%s]' % (_mc, col, flag, _mc)

        if nl: write_color(fmt.format(text, sta), file=sys.stdout, loglevel=3)
        else:  write_color(fmt.format(text, sta), file=sys.stdout, loglevel=0)
    else:
        write_color(fmt.format(text), file=sys.stdout, loglevel=3)


def print_progress(text, r, nl=None):
    width = get_line_width()

    mwidth = int(width * 6 / 10)
    if mwidth < 50:
        mwidth = 50

    mwidth = mwidth + 1

    bwidth = width - mwidth - 7
    # 7 = 4 (percent number) + 1 (space) + 2 ([])

    if nl == None:
        if re.match("^.*\n\s*$", text, re.MULTILINE): nl = True
        else:                                         nl = False

    if text: text = text.strip()

    barstr = int(r*bwidth)*'#' + (bwidth-int(r*bwidth))*'='
    fmt = '\r {0:<%s} [{1}] {2:3d}%%' % (mwidth - 2)

    if nl: fmt = fmt + '\n'
    else: fmt = fmt + '\r'

    out = fmt.format(text, barstr, int(100*r))
    sys.stdout.write(out)
    sys.stdout.flush()
    if nl: write_log(out, level=3)




def ask_question_string(question):
    write_color('%s ? #*w%s ' % (_mc, question), file=sys.stderr, loglevel=3)
    ans = input()
    write_log('%s\n' % ans, level=3)
    return ans

def ask_question_yesno(question, default=None):
    if default == 'yes':    hint = '[Y/n]'
    elif default == 'no':   hint = '[y/N]'
    else:                   hint = '[y/n]'
    while True:
        val = ask_question_string(question + ' ' + hint)
        val = val.strip().lower()
        if val == 'y':              return 'yes'
        elif val == 'n':            return 'no'
        elif default and val == '': return default
        else: write_color('Invalid answer.\n', loglevel=3)


# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
