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

import os

from collections import OrderedDict

class PathDict(object):
    """A dictionary that maps data objects to paths. Every subpath inherits the data
    object from its parent."""
    class _node(object):
        def __init__(self, path):
            self.path = path
            self.sub = OrderedDict()
            self.data = None
            self.leaf = False    # If leaf if true, the node implicitly contains all its subdirectories


    def __init__(self, dic={}):
        self.tree = PathDict._node(path="")
        if type(dic) == type([]):
            for p, d in dic: self._setdata(self.tree, p, d)

        else:
            for p, d in dic.items(): self._setdata(self.tree, p, d)


    def _splitpath(self, p):
        """splits the first directory in path"""
        L = p.split('/', 1)
        if len(L) > 1:    return L[0], L[1]
        elif len(L) == 1: return L[0], None
        else:             return None, None


    def _checkpath(self, tree, p):
        """Checks whether the path p is a subdirectory of some path in the structure"""
        head, tail = self._splitpath(p)
        if not head in tree.sub: return tree.leaf

        if tail: return self._checkpath(tree.sub[head], tail)
        else:    return tree.sub[head].leaf


    def _getdata(self, tree, p):
        head, tail = self._splitpath(p)
        if not head in tree.sub:
            if tree.leaf: return tree
            else: raise KeyError("Path %s not found" % os.path.join(tree.path, p))

        if tail: return self._getdata(tree.sub[head], tail)
        else:
            if tree.sub[head].leaf: return tree.sub[head]
            else: raise KeyError("Path %s not found" % os.path.join(tree.path, p))


    def _setdata(self, tree, p, data):
        head, tail = self._splitpath(p)
        path = os.path.join(tree.path, head)
        if not head in tree.sub: tree.sub[head] = PathDict._node(path=path)

        if tail: self._setdata(tree.sub[head], tail, data)
        else:    tree.sub[head].leaf = True

        if tail: tree.sub[head].data = tree.data
        else:    tree.sub[head].data = data


    def _leafgen(self, tree):
        for p, val in tree.sub.items():
            path = os.path.join(tree.path, p)
            if val.leaf:
                yield (path, val.data)
            else:
                for k, v in self._leafgen(val):
                    yield (k, v)


    def intersection(self, dic):
        new = PathDict()
        for p, val in self.items():
            self_node = self._getdata(self.tree, p)
            try:
                dic_node = dic._getdata(dic.tree, p)
                new[p] = val

            except KeyError:
                continue

        for p, val in dic.items():
            dic_node = self._getdata(dic.tree, p)
            try:
                self_node = dic._getdata(self.tree, p)
                new[p] = val

            except KeyError:
                continue

        return new


    def items(self):
        """Returns a list of tuples of key, value pairs for the nodes marked as leaf"""
        return self._leafgen(self.tree)


    def __and__(self, dic):
        return self.intersection(dic)

    def __contains__(self, key):
        return self._checkpath(self.tree, key)

    def __getitem__(self, key):
        return self._getdata(self.tree, key).data

    def __setitem__(self, key, val):
        self._setdata(self.tree, key, val)

    def __str__(self):
        return '{%s}' % (', '.join(["'%s': %s" % (p, str(val)) for p, val in self.items()]))
