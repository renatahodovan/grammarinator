# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .model import Model


class CustomWeightsModel(Model):
    """
    This model enables to scale the probabilities of generating certain
    alternatives. The input dictionary containing the weights for scaling must
    look like: `dict[(rule_name, alternation_idx, alternative_idx)] = weight`.
    """

    def __init__(self, model, weights):
        """
        :param Model model: The underlying model.
        :param dict[tuple,float] weights: Custom multipliers assigned to alternatives.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of :meth:`choice`, while
               the third element corresponds to the indices of the ``weights`` parameter.
        """
        self._model = model
        self._weights = weights

    def choice(self, node, idx, weights):
        """
        Transitively calls the ``choice`` method of the underlying
        model with custom multipliers applied to ``weights``.
        """
        return self._model.choice(node, idx, [w * self._weights.get((node.name, idx, i), 1) for i, w in enumerate(weights)])

    def quantify(self, node, idx, min, max):
        """
        Trampoline to the ``quantify`` method of the underlying model.
        """
        yield from self._model.quantify(node, idx, min, max)

    def charset(self, node, idx, chars):
        """
        Trampoline to the ``charset`` method of the underlying model.
        """
        return self._model.charset(node, idx, chars)
