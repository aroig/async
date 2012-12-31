#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# texa - A command line tool to assist in latex document preparation.
# Copyright 2011,2012 Abdó Roig-Maranges <abdo.roig@gmail.com>
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
from texa import __version__

setup(name         = 'Texa',
      version      = __version__,
      license      = 'GNU GPLv3',
      description  = 'A command line tool to assist in latex document preparation',
      author       = 'Abdó Roig-Maranges',
      author_email = 'abdo.roig@gmail.com',
      packages     = ['texa', 'texa.archui', 'texa.searchparser', 'texa.vcs', 'texa.latex'],
      scripts      = ['bin/texa'])
