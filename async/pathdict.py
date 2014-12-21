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

import os

from collections import OrderedDict

class PathDict(object):
    """A dictionary that maps paths to data objects. Every subpath inherits the data
    object from its parent."""

    class _node(object):
        def __init__(self, path, leaf=False, ignore=False, data=None):
            self.path = path
            self.sub = OrderedDict()
            self.data = data
            self.leaf = leaf      # If leaf is true, the node implicitly affects all its subdirectories
            self.ignore = ignore  # If ignore is true, ignore this and all subdirs.

        def copy(self):
            new = PathDict._node(path=self.path,
                                 data=self.data,
                                 leaf=self.leaf,
                                 ignore=self.ignore)

            for k, v in self.sub.items():
                new.sub[k] = self.sub[k].copy()

        def __eq__(self, other):
            if not self.path == other.path: return False
            if not self.sub == other.sub: return False
            if not self.leaf == other.leaf: return False
            if not self.ignore == other.ignore: return False
            if not self.data == other.data: return False
            return True



    def __init__(self, dic={}, ignore={}):
        # root tree is a leaf that ignores everything.
        self.tree = PathDict._node(path="", leaf=True, ignore=True)

        # add data in dic
        if type(dic) == type([]):
            for p, d in dic: self._addleaf(self.tree, p, d, ignore=False)
        else:
            for p, d in dic.items(): self._addleaf(self.tree, p, d, ignore=False)

        # ignore paths in ignore
        if type(dic) == type([]):
            for p, d in ignore: self._addleaf(self.tree, p, d, ignore=True)
        else:
            for p, d in ignore.items(): self._addleaf(self.tree, p, d, ignore=True)




    # Internal primitives   #
    # --------------------- #

    def _splitpath(self, p):
        """splits the first directory in path"""
        if p == None:     return None, None

        L = p.split('/', 1)
        if len(L) > 1:    return L[0], L[1]
        elif len(L) == 1: return L[0], None
        else:             return None, None


    def _checkpath(self, tree, leafparent, p):
        """Checks whether the path p is a subdirectory of some path in the structure"""
        head, tail = self._splitpath(p)
        if tree.leaf: leafparent = tree

        if head and head in tree.sub: return self._checkpath(tree.sub[head], leafparent, tail)
        else:                         return not leafparent.ignore


    def _getdata(self, tree, leafparent, p):
        """Returns the tree leaf associated to path p, or KeyError if not found"""
        head, tail = self._splitpath(p)
        if tree.leaf: leafparent = tree

        if head and head in tree.sub: return self._getdata(tree.sub[head], leafparent, tail)
        elif not leafparent.ignore:   return leafparent
        else:                         raise KeyError("Path '%s' not found" % tree.path)


    def _addleaf(self, tree, p, data, ignore):
        """Adds a leaf to the tree"""
        head, tail = self._splitpath(p)

        if head == None:
            tree.leaf = True
            tree.data = data
            tree.ignore = ignore

        else:
            if not head in tree.sub:
                tree.sub[head] = PathDict._node(path=os.path.join(tree.path, head))

            self._addleaf(tree.sub[head], tail, data, ignore=ignore)


    def _leafgen(self, tree):
        """Generator that runs over all leaves"""
        for p, val in tree.sub.items():
            if val.leaf:
                yield (val.path, val)

            for k, v in self._leafgen(val):
                yield (k, v)




    # Interface             #
    # --------------------- #

    def copy(self, dic):
        new = PathDict()
        new.tree = self.tree.copy()
        return new


    def complementary(self):
        """Computes the complementary of a pathdict.

        """

        new = PathDict()

        for p, val in self._leafgen(self.tree):
            new._addleaf(new.tree, val.path, val.data, ignore=not val.ignore)
        return new


    def intersection(self, dic):
        """Computes the intersection of pathdicts. If some node is a leaf on both sides the data
        provided by self is the chosen one.

        """

        new = PathDict()

        for p, val in dic._leafgen(dic.tree):
            if val.ignore or p in self:
                new._addleaf(new.tree, val.path, val.data, ignore=val.ignore)

        for p, val in self._leafgen(self.tree):
            if val.ignore or p in dic:
                new._addleaf(new.tree, val.path, val.data, ignore=val.ignore)

        return new


    def union(self, dic):
        """Computes the union of pathdicts. If some node is a leaf on both sides the data provided
        by self is the chosen one.

        """

        new = PathDict()

        for p, val in dic._leafgen(dic.tree):
            if not val.ignore or not p in self:
                new._addleaf(new.tree, val.path, val.data, ignore=val.ignore)

        for p, val in self._leafgen(self.tree):
            if not val.ignore or not p in dic:
                new._addleaf(new.tree, val.path, val.data, ignore=val.ignore)

        return new


    def subtract(self, dic):
        """Computes the subtraction of pathdicts. If some node is a leaf on both sides the data
        provided by self is the chosen one.

        """

        new = PathDict()

        for p, val in dic._leafgen(dic.tree):
            if not val.ignore or p in dic:
                new._addleaf(new.tree, val.path, val.data, ignore=not val.ignore)

        for p, val in self._leafgen(self.tree):
            if val.ignore or not p in dic:
                new._addleaf(new.tree, val.path, val.data, ignore=val.ignore)

        return new


    def get(self, key, default=None):
        try:
            return self._getdata(self.tree, self.tree, key).data
        except KeyError:
            return default


    def remove(self, key):
        self._addleaf(self.tree, key, None, ignore=True)


    def data(self, keys=None, ignore=[]):
        """Extract an OrderedDict, from the PathDict. If keys is provided, Use those keys for the
           OrderedDict, in that same order. Do not complain on KeyError, just put None as
           data.

        """
        if keys == None: keys = list(self.keys())
        ig = PathDict(dic={p: p for p in ignore})

        dic = OrderedDict()
        for k in keys:
            if not k in ig:
                dic[k] = self.get(k, None)

        return dic


    def ignored_items(self):
        """Generator producing a list of ignored paths"""
        for k, v in self._leafgen(self.tree):
            if v.ignore:
                yield (v.path, v.data)

    def ignored_keys(self):
        """Generator producing a list of keys for the ignored paths"""
        for k, d in self.ignored_items():
            yield d

    def ignored_values(self):
        """Generator producing a list of values for the ignored paths"""
        for k, d in self.ignored_items():
            yield d

    def items(self):
        """Generator producing a list of tuples of key, value pairs
           for the nodes marked as leaf"""
        for k, v in self._leafgen(self.tree):
            if not v.ignore:
                yield (v.path, v.data)

    def keys(self):
        """Generator producing a list of keys for the nodes marked as leaf"""
        for k, d in self.items():
            yield k

    def values(self):
        """Generator producing a list of keys for the nodes marked as leaf"""
        for k, d in self.items():
            yield d

    def __and__(self, dic):
        return self.intersection(dic)

    def __or__(self, dic):
        return self.union(dic)

    def __sub__(self, dic):
        return self.subtract(dic)

    def __contains__(self, key):
        return self._checkpath(self.tree, self.tree, key)

    def __getitem__(self, key):
        return self._getdata(self.tree, self.tree, key).data

    def __setitem__(self, key, val):
        self._addleaf(self.tree, key, val, ignore=False)

    def __delitem__(self, key):
        self._addleaf(self.tree, key, None, ignore=True)

    def __eq__(self, other):
        return self.tree == other.tree

    def __str__(self):
        return '{%s | %s}' % (', '.join(["'%s': %s" % (p, str(val)) for p, val in self.items()]),
                              ', '.join(["'%s': %s" % (p, str(val)) for p, val in self.ignored_items()]))

    def __repr__(self):
        return str(self)
