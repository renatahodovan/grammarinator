# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class CooldownModel(object):

    def __init__(self, model, weights=None, cooldown=1.0):
        self._model = model
        self._weights = weights or dict()
        self._cooldown = cooldown

    def choice(self, node, idx, choices):
        i = self._model.choice(node, idx, [w * self._weights.get((node.name, i), 1) for i, w in enumerate(choices)])
        self._weights[(node.name, i)] = self._weights.get((node.name, i), 1) * self._cooldown
        return i

    def quantify(self, node, idx, min, max):
        yield from self._model.quantify(node, idx, min, max)

    def charset(self, node, idx, chars):
        return self._model.charset(node, idx, chars)
