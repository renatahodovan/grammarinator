# Copyright (c) 2020-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from typing import Optional, Union

from .model import Model
from .rule import Rule


class WeightedModel(Model):
    """
    Custom model (or model wrapper) that pre-multiplies the weights of
    alternatives before calling the underlying model.
    """

    def __init__(self, model: Model, *, weights: Optional[dict[tuple[str, int, int], float]] = None) -> None:
        """
        :param model: The underlying model.
        :param weights: Multipliers of alternatives. The keys of the dictionary
            are tuples in the form of ``(str, int, int)``, each denoting an
            alternative: the first element specifies the name of the rule that
            contains the alternative, the second element specifies the index of
            the alternation containing the alternative within the rule, and the
            third element specifies the index of the alternative within the
            alternation (both indices start counting from 0). The first and
            second elements correspond to the ``node`` and ``idx`` parameters of
            :meth:`choice`, while the third element corresponds to the indices
            of the ``weights`` parameter.
        """
        self._model: Model = model
        self._weights: dict[tuple[str, int, int], float] = weights or {}

    def choice(self, node: Rule, idx: int, weights: list[float]) -> int:
        """
        Transitively calls the ``choice`` method of the underlying model with
        multipliers applied to ``weights`` first.
        """
        return self._model.choice(node, idx, [w * self._weights.get((node.name, idx, i), 1) for i, w in enumerate(weights)])

    def quantify(self, node: Rule, idx: int, cnt: int, start: int, stop: Union[int, float]) -> bool:
        """
        Trampoline to the ``quantify`` method of the underlying model.
        """
        return self._model.quantify(node, idx, cnt, start, stop)

    def charset(self, node: Rule, idx: int, chars: tuple[int, ...]) -> str:
        """
        Trampoline to the ``charset`` method of the underlying model.
        """
        return self._model.charset(node, idx, chars)
