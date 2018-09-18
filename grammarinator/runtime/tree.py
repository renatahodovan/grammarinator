# Copyright (c) 2017-2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import pickle

from copy import copy, deepcopy


class Tree(object):

    extension = '.grt'

    def __init__(self, root):
        self.root = root
        self.node_dict = None

    def annotate(self):
        """
        Add a dictionary to the current object which is indexed by node names
        and contains nodes with the given name.
        Furthermore, it sets the level and depth fields for every node.
        Level field tells how far a node is from root.
        Depth field shows how deep the tree is below the node.
        """
        def _annotate(current, level):
            """
            :param current: The node to start annotation from (initially it's the root).
            :param level: Level to start annotation from.
            :return: Depth of the current node.
            """
            current.level = level
            level += 1

            if current.name not in self.node_dict:
                self.node_dict[current.name] = set()
            self.node_dict[current.name].add(current)

            current.depth = 0
            if current.children:
                for child in current.children:
                    child.depth = _annotate(child, level)
                    current.depth = max(current.depth, child.depth + 1)

            return current.depth

        self.node_dict = dict()
        _annotate(self.root, 0)

    @staticmethod
    def load(fn):
        with open(fn, 'rb') as f:
            return pickle.load(f)

    def save(self, fn, max_depth=float('inf')):
        self.annotate()

        if self.root.depth <= max_depth:
            with open(fn, 'wb') as f:
                pickle.dump(self, f)

    def __str__(self):
        return str(self.root)


class BaseRule(object):

    children = []

    def __init__(self, *, name):
        self.name = name
        self.children = []
        self.parent = None
        self.level = None
        self.depth = None

    # Support for += operation.
    def __iadd__(self, child):
        if isinstance(child, list):
            self.add_children(child)
        else:
            self.add_child(child)
        return self

    def copy(self):
        return copy(self)

    def deepcopy(self):
        return deepcopy(self)

    @property
    def left_sibling(self):
        try:
            self_idx = self.parent.children.index(self)
            return self.parent.children[self_idx - 1] if self_idx > 0 else None
        except ValueError:
            return None

    @property
    def right_sibling(self):
        try:
            self_idx = self.parent.children.index(self)
            return self.parent.children[self_idx + 1] if self_idx < len(self.parent.children) - 1 else None
        except ValueError:
            return None

    @property
    def last_child(self):
        return self.children[-1] if self.children else None

    @last_child.setter
    def last_child(self, node):
        self.children.pop()
        self.add_child(node)

    def insert_child(self, idx, child):
        if not child:
            return

        child.parent = self
        self.children.insert(idx, child)

    def add_child(self, child):
        if child is None:
            return

        self.children.append(child)
        child.parent = self

    def add_children(self, children):
        for child in children:
            self.add_child(child)

    def replace(self, other):
        if self.parent:
            self.parent.children[self.parent.children.index(self)] = other
            other.parent = self.parent
            self.parent = None
        return other

    def delete(self):
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def __str__(self):
        return ''.join([str(child) for child in self.children])

    def __getattr__(self, item):
        result = [child for child in self.children if child.name == item]

        if not result:
            raise AttributeError('No child with name \'{name}\'.'.format(name=item))

        return result[0] if len(result) == 1 else result


class UnparserRule(BaseRule):
    pass


class UnlexerRule(BaseRule):

    def __init__(self, *, name=None, src=None):
        super(UnlexerRule, self).__init__(name=name)
        self.src = src

    def __str__(self):
        return self.src or super(UnlexerRule, self).__str__()
