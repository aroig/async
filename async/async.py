#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
# hypathia - A tool to sync calibre to my ebook reader.
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

import re
import os
import time
import subprocess
import sys
import paramiko
import glob
import shutil



# vim: expandtab:shiftwidth=4:tabstop=4:softtabstop=4:textwidth=80
