# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from copy import copy, deepcopy


class BaseRule(object):

    def __init__(self, *, name):
        self.name = name
        self.children = []
        self.parent = None

    # Support for += operation.
    def __iadd__(self, child):
        if type(child) == list:
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
        if not child:
            return

        self.children.append(child)
        child.parent = self

    def add_children(self, children):
        for child in children:
            self.add_child(child)

    def __str__(self):
        return ''.join([str(child) for child in self.children])


class UnparserRule(BaseRule):
    pass


class UnlexerRule(BaseRule):

    def __init__(self, *, name=None, src=None):
        super(UnlexerRule, self).__init__(name=name)
        self.src = src

    def __str__(self):
        return self.src or super(UnlexerRule, self).__str__()
