# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import pickle

from copy import deepcopy
from math import inf


class Tree(object):

    extension = '.grt'

    def __init__(self, root):
        self.root = root
        self.node_dict = None

    def __deepcopy__(self, memo):
        tree = Tree(deepcopy(self.root, memo=memo))
        tree.annotate()
        return tree

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

        self.node_dict = {}
        _annotate(self.root, 0)

    @staticmethod
    def load(fn):
        with open(fn, 'rb') as f:
            return pickle.load(f)

    def save(self, fn, max_depth=inf):
        self.annotate()

        if self.root.depth <= max_depth:
            with open(fn, 'wb') as f:
                pickle.dump(self, f)

    def print(self):

        def _walk(node):
            nonlocal indent

            if isinstance(node, UnparserRule):
                print(f'{"  " * indent}{node.name}')
                indent += 1
                for child in node.children:
                    _walk(child)
                indent -= 1

            else:
                toplevel_unlexerrule = not node.parent or isinstance(node.parent, UnparserRule)
                if toplevel_unlexerrule:
                    print(f'{"  " * indent}{node.name or ""}{":" if node.name else ""}"', end='')

                if node.src is not None:
                    print(node.src, end='')
                else:
                    for child in node.children:
                        _walk(child)

                if toplevel_unlexerrule:
                    print('"')

        indent = 0
        _walk(self.root)

    def __str__(self):
        return str(self.root)


class BaseRule(object):

    children = []

    def __init__(self, *, name, parent=None):
        self.name = name
        self.parent = parent
        if parent:
            parent += self
        self.children = []
        self.level = None
        self.depth = None

    # Support for += operation.
    def __iadd__(self, child):
        if isinstance(child, list):
            self.add_children(child)
        else:
            self.add_child(child)
        return self

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
        self.children.pop().parent = None
        self.add_child(node)

    def insert_child(self, idx, node):
        if not node:
            return

        node.parent = self
        self.children.insert(idx, node)

    def add_child(self, node):
        if node is None:
            return

        self.children.append(node)
        node.parent = self

    def add_children(self, nodes):
        for node in nodes:
            self.add_child(node)

    def replace(self, node):
        if self.parent and node is not self:
            self.parent.children[self.parent.children.index(self)] = node
            node.parent = self.parent
            self.parent = None
        return node

    def delete(self):
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None

    def __str__(self):
        return ''.join(str(child) for child in self.children)

    def __getattr__(self, item):
        # This check is needed to avoid infinite recursions when loading a tree
        # with pickle. In such cases, the loaded instance is prepared by
        # creating an empty object with the expected ``__class__`` and by
        # restoring the saved attributes (without calling ``__init__``).
        # During this operation, the ``__set_state__`` method of the target
        # class is tried to be called, if it exists. Otherwise, ``__getattr__``
        # throws an ``AttributeError``. However, if the instantiation of this
        # error object tries to access any field that is not yet added by
        # pickle, then it throws another ``AttributeError``, causing an
        # infinite recursion. Filtering for the field names, that are used
        # later in this method, eliminates the issue.
        if item in ['name', 'children']:
            raise AttributeError()

        result = [child for child in self.children if child.name == item]

        if not result:
            raise AttributeError(f'[{self.name}] No child with name {item!r} {[child.name for child in self.children]}.')

        return result[0] if len(result) == 1 else result


class UnparserRule(BaseRule):
    pass


class UnlexerRule(BaseRule):

    def __init__(self, *, name=None, parent=None, src=None):
        super().__init__(name=name, parent=parent)
        self.src = src

    def __str__(self):
        return self.src or super().__str__()
