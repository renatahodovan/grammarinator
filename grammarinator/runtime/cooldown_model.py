# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from contextlib import nullcontext


class CooldownModel(object):

    def __init__(self, model, *, cooldown=1.0, weights=None, lock=None):
        self._model = model
        self._cooldown = cooldown
        self._weights = weights or {}
        self._lock = lock or nullcontext()

    def choice(self, node, idx, weights):
        c = self._model.choice(node, idx, [w * self._weights.get((node.name, idx, i), 1) for i, w in enumerate(weights)])
        with self._lock:
            self._weights[(node.name, idx, c)] = self._weights.get((node.name, idx, c), 1) * self._cooldown
            wsum = sum(self._weights.get((node.name, idx, i), 1) for i in range(len(weights)))
            for i in range(len(weights)):
                self._weights[(node.name, idx, i)] = self._weights.get((node.name, idx, i), 1) / wsum
        return c

    def quantify(self, node, idx, min, max):
        yield from self._model.quantify(node, idx, min, max)

    def charset(self, node, idx, chars):
        return self._model.charset(node, idx, chars)
