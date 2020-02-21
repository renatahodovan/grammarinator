# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class CooldownModel(object):

    def __init__(self, model, weights=None, cooldown=1.0):
        self.model = model
        self.weights = weights or dict()
        self.cooldown = cooldown

    def choice(self, name, choices):
        i = self.model.choice(name, [w * self.weights.get((name, i), 1) for i, w in enumerate(choices)])
        self.weights[(name, i)] = self.weights.get((name, i), 1) * self.cooldown
        return i

    def quantify(self, min, max):
        yield from self.model.quantify(min=min, max=max)
