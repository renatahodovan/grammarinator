# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from math import inf

from .default_model import DefaultModel
from .rule import UnlexerRule, UnparserRule

logger = logging.getLogger(__name__)


class RuleContext(object):
    # Context manager wrapping rule generations. It is responsible for
    # keeping track of the value of `max_depth` and for transitively calling the
    # enter and exit methods of the registered listeners.

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


class UnlexerRuleContext(RuleContext):
    """
    Subclass of :class:`RuleContext` handling unlexer rules.
    """

    def __init__(self, gen, name, parent=None):
        super().__init__(gen, parent if isinstance(parent, UnlexerRule) else UnlexerRule(name=name, parent=parent))


class UnparserRuleContext(RuleContext):
    """
    Subclass of :class:`RuleContext` handling unparser rules.
    """

    def __init__(self, gen, name, parent=None):
        super().__init__(gen, UnparserRule(name=name, parent=parent))


class AlternationContext(object):
    # Context manager wrapping alternations. It is responsible for filtering
    # the alternatives available within the maximum depth. Otherwise, if nothing
    # is available (possibly due to some custom predicates or rule definitions),
    # then it temporarily raises the maximum depth to the minimum value
    # required to finish the generation.

    def __init__(self, gen, min_depths, conditions):
        self._gen = gen
        self._min_depths = min_depths
        self._conditions = conditions
        self._orig_depth = gen._max_depth

    def __enter__(self):
        filtered_weights = [w if self._min_depths[i] <= self._gen._max_depth else 0 for i, w in enumerate(self._conditions)]
        if sum(filtered_weights) > 0:
            return filtered_weights
        max_depth = min(self._min_depths[i] if w > 0 else inf for i, w in enumerate(self._conditions))
        logger.debug('max_depth must be temporarily set from %s to %s', self._gen._max_depth, max_depth)
        self._gen._max_depth = max_depth
        return [w if self._min_depths[i] <= self._gen._max_depth else 0 for i, w in enumerate(self._conditions)]

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._gen._max_depth = self._orig_depth


class QuantifierContext(object):

    def __init__(self, gen, idx, min, max, min_depth):
        self._gen = gen
        self._idx = idx
        self._min = min
        self._max = max
        self._min_depth = min_depth
        self._cnt = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return None

    def __call__(self, node):
        if self._cnt < self._min:
            self._cnt += 1
            return True

        # Check whether the quantified expression is available in the given size limits.
        if self._cnt < self._max and self._min_depth <= self._gen._max_depth and self._gen._model.quantify(node, self._idx, self._cnt, self._min, self._max):
            self._cnt += 1
            return True

        return False


class Generator(object):
    """
    Base class of the generated Generators. Stores the decision model, the listeners,
    and additional internal state used during generation.
    """

    def __init__(self, *, model=None, listeners=None, max_depth=inf):
        """
        :param Model model: Model object responsible for every decision during the generation.
               (default: :class:`DefaultModel`).
        :param list[Listener] listeners: Listeners that get notified whenever a
               rule is entered or exited.
        :param int or float max_depth: Maximum depth of the generated tree (default: ``inf``).
        """
        self._model = model or DefaultModel()
        self._max_depth = max_depth
        self._listeners = listeners or []

    def _enter_rule(self, node):
        for listener in self._listeners:
            listener.enter_rule(node)

    def _exit_rule(self, node):
        for listener in reversed(self._listeners):
            listener.exit_rule(node)
