#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# async - A tool to manage and sync different machines
# Copyright 2012-2014 Abdó Roig-Maranges <abdo.roig@gmail.com>
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

import random
import unittest

from async.pathdict import PathDict
from collections import OrderedDict

class PathDictTests(unittest.TestCase):

    def setUp(self):
        self.A = PathDict(dic=[('a', 1), ('b', 2), ('a/c',3), ('b/d/g',5)], ignore=[('b/d', 4)])
        self.B = PathDict(dic=[('a', 10), ('b/d/e', 20)])

    def test_enumeration(self):
        self.assertEqual(list(self.A.items()), [('a', 1), ('a/c',3), ('b', 2), ('b/d/g',5)])
        self.assertEqual(list(self.A.ignored_items()), [('b/d', 4)])
        self.assertEqual(self.A.data(keys=['b', 'a/c']), OrderedDict([('b', 2), ('a/c', 3)]))

    def test_membership(self):
        self.assertEqual(self.A.get('a'), 1)
        self.assertEqual(self.A.get('a/f'), 1)
        self.assertEqual(self.A.get('a/c'), 3)
        self.assertEqual(self.A.get('b/d'), None)
        self.assertEqual(self.A.get('b/d/g'), 5)

    def test_union(self):
        Ur = PathDict(dic=[('a', 1), ('b', 2), ('b/d/e', 20), ('b/d/g', 5), ('a/c', 3)], ignore=[('b/d', 4)])
        Uc = self.A | self.B
        self.assertEqual(Uc, Ur)

    def test_intersection(self):
        Ir = PathDict(dic=[('a', 1), ('a/c', 3)], ignore=[('b/d', 4)])
        Ic = self.A & self.B
        self.assertEqual(Ic, Ir)


if __name__ == '__main__':
    unittest.main()
