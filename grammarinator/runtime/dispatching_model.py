# Copyright (c) 2020-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .default_model import DefaultModel
from .rule import Rule


class DispatchingModel(DefaultModel):
    """
    Base class of custom models that aim to override the decisions in
    specific rules. To override a decision point, the subclass must
    define methods in the form of ``choice_{rule_name}``, ``quantify_{rule_name}``
    or ``charset_{rule_name}`` - with the same signature as their counterparts
    in :class:`DefaultModel` - in case of overriding an alternation, quantifier
    or charset decision, respectively.
    """

    def choice(self, node: Rule, idx: int, weights: list[float]) -> int:
        """
        Trampoline to the ``choice_{node.name}`` method of the subclassed model, if it exists.
        Otherwise, it calls the default implementation (:meth:`DefaultModel.choice`).
        """
        name = 'choice_' + node.name
        return (getattr(self, name) if hasattr(self, name) else super().choice)(node, idx, weights)

    def quantify(self, node: Rule, idx: int, cnt: int, start: int, stop: int | float) -> bool:
        """
        Trampoline to the ``quantify_{node.name}`` method of the subclassed model, if it exists.
        Otherwise, it calls the default implementation (:meth:`DefaultModel.quantify`).
        """
        name = 'quantify_' + node.name
        return (getattr(self, name) if hasattr(self, name) else super().quantify)(node, idx, cnt, start, stop)

    def charset(self, node: Rule, idx: int, chars: tuple[int, ...]) -> str:
        """
        Trampoline to the ``charset_{node.name}`` method of the subclassed model, if it exists.
        Otherwise, it calls the default implementation (:meth:`DefaultModel.charset`).
        """
        name = 'charset_' + node.name
        return (getattr(self, name) if hasattr(self, name) else super().charset)(node, idx, chars)
