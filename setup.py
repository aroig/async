#!/usr/bin/env python
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

from distutils.core import setup
from async import __version__

setup(name         = 'async',
      version      = __version__,
      license      = 'GNU GPLv3',
      description  = 'A tool to manage and sync different machines',
      author       = 'Abdó Roig-Maranges',
      author_email = 'abdo.roig@gmail.com',
      packages     = ['async', 'async.archui', 'async.directories', 'async.hosts'],
      scripts      = ['bin/async'])
