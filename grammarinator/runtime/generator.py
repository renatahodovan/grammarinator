# Copyright (c) 2017-2022 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from math import inf

from .default_model import DefaultModel


class RuleContext(object):

    def __init__(self, gen, node):
        self._gen = gen
        self._node = node

    def __enter__(self):
        self._gen._max_depth -= 1
        self._gen._enter_rule(self._node)
        return self._node

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._gen._exit_rule(self._node)
        self._gen._max_depth += 1


class Generator(object):

    def __init__(self, *, model=None, max_depth=inf):
        self._model = model or DefaultModel()
        self._max_depth = max_depth
        self._listeners = []

    def _enter_rule(self, node):
        for listener in self._listeners:
            listener.enter_rule(node)

    def _exit_rule(self, node):
        for listener in reversed(self._listeners):
            listener.exit_rule(node)
