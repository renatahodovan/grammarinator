# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from math import inf

from ..model import DefaultModel


def depthcontrol(fn):
    def controlled_fn(obj, *args, **kwargs):
        obj.max_depth -= 1
        try:
            result = fn(obj, *args, **kwargs)
        finally:
            obj.max_depth += 1
        return result

    controlled_fn.__name__ = fn.__name__
    return controlled_fn


class Generator(object):

    def __init__(self, *, model=None, max_depth=inf):
        self.model = model or DefaultModel()
        self.max_depth = max_depth
        self.listeners = []

    def enter_rule(self, node):
        for listener in self.listeners:
            listener.enter_rule(node)

    def exit_rule(self, node):
        for listener in reversed(self.listeners):
            listener.exit_rule(node)
