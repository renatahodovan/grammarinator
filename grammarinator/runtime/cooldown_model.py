# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from contextlib import nullcontext


class CooldownModel(object):
    """
    Custom model (or model wrapper) that updates (practically downscales) the
    weights of alternatives chosen by the underlying model.
    """

    def __init__(self, model, *, cooldown=1.0, weights=None, lock=None):
        """
        :param model: The underlying model.
        :param float cooldown: The cooldown factor (default: 1.0, meaning no cooldown).
        :param dict[tuple,float] weights: Cooldown weights of alternatives. It is only useful, if the same
               dictionary object is passed to every invocation of this class so that the decisions made
               during test case generation can affect those that follow.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of  :meth:`choice`, while
               the third element corresponds to the indices of the ``weights`` parameter.
        :param multiprocessing.Lock lock: Lock object when generating in parallel (optional).
        """
        self._model = model
        self._cooldown = cooldown
        self._weights = weights or {}
        self._lock = lock or nullcontext()

    def choice(self, node, idx, weights):
        """
        Method called by the generated fuzzer to choose an alternative from an
        alternation. Transitively calls the ``choice`` method of the underlying
        model with cooldown multipliers applied to ``weights`` first, and updates
        the cooldown multiplier of the chosen alternative with the cooldown factor afterwards.

        :param BaseRule node: Rule node object containing the alternation to choose alternative from.
        :param int idx: Index of the alternation inside the rule.
        :param list[float] weights: Weights assigned to the alternatives in the grammar using semantic predicates.
        :return: The index of the chosen alternation.
        :rtype: int
        """
        c = self._model.choice(node, idx, [w * self._weights.get((node.name, idx, i), 1) for i, w in enumerate(weights)])
        with self._lock:
            self._weights[(node.name, idx, c)] = self._weights.get((node.name, idx, c), 1) * self._cooldown
            wsum = sum(self._weights.get((node.name, idx, i), 1) for i in range(len(weights)))
            for i in range(len(weights)):
                self._weights[(node.name, idx, i)] = self._weights.get((node.name, idx, i), 1) / wsum
        return c

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
