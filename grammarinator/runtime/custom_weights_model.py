# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

class CustomWeightsModel(object):
    """
    This model enables to scale the probabilities of generating certain
    alternatives. The input dictionary containing the weights for scaling must
    look like: `dict[(rule_name, alternation_idx, alternative_idx)] = weight`.
    """

    def __init__(self, model, weights):
        self._model = model
        self._weights = weights

    def choice(self, node, idx, weights):
        return self._model.choice(node, idx, [w * self._weights.get((node.name, idx, i), 1) for i, w in enumerate(weights)])

    def quantify(self, node, idx, min, max):
        yield from self._model.quantify(node, idx, min, max)

    def charset(self, node, idx, chars):
        return self._model.charset(node, idx, chars)
