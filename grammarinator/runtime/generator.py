# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from .default_model import DefaultModel
from .rule import RuleSize, UnlexerRule, UnparserRule

logger = logging.getLogger(__name__)


class RuleContext:
    # Context manager wrapping rule generations. It is responsible for
    # keeping track of the value of `max_depth` and for transitively calling the
    # enter and exit methods of the registered listeners.

    def __init__(self, gen, node):
        self._gen = gen
        self._node = node

    def __enter__(self):
        # Increment current depth by 1 before entering the next level.
        self._gen._size.depth += 1
        self._gen._enter_rule(self._node)
        return self._node

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._gen._exit_rule(self._node)
        # Decrementing current depth after finishing a rule.
        self._gen._size.depth -= 1


class UnlexerRuleContext(RuleContext):
    # Subclass of :class:`RuleContext` handling unlexer rules.

    def __init__(self, gen, name, parent=None):
        if isinstance(parent, UnlexerRule):
            super().__init__(gen, parent)
            self._start_depth = None
        else:
            node = UnlexerRule(name=name)
            if parent:
                parent += node
            super().__init__(gen, node)
            self._start_depth = self._gen._size.depth

    def __enter__(self):
        node = super().__enter__()
        # Increment token count with the current token.
        self._gen._size.tokens += 1
        # Keep track of the depth and token count of lexer rules, since these
        # values cannot be calculated from the output tree.
        node.size.tokens += 1
        if self._gen._size.depth > node.size.depth:
            node.size.depth = self._gen._size.depth
        return node

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        if self._start_depth is not None:
            self._node.size.depth -= self._start_depth


class UnparserRuleContext(RuleContext):
    # Subclass of :class:`RuleContext` handling unparser rules.

    def __init__(self, gen, name, parent=None):
        node = UnparserRule(name=name)
        if parent:
            parent += node
        super().__init__(gen, node)


class AlternationContext:
    # Context manager wrapping alternations. It is responsible for filtering
    # the alternatives available within the maximum depth, token size and
    # decisions. Otherwise, if nothing is available (possibly due to some
    # custom predicates or rule definitions or contradicting size limits),
    # then it temporarily raises the maximum size to the minimum value
    # required to finish the generation.

    def __init__(self, gen, idx, min_sizes, reserve, conditions):
        self._gen = gen
        self._idx = idx
        self._min_sizes = min_sizes
        self._reserve = reserve  # Minimum number of remaining tokens needed by the right siblings.
        self._conditions = conditions  # Boolean values enabling or disabling the certain alternatives.
        self._orig_depth_limit = self._gen._limit.depth
        # Reserve token budget for the rest of the test case by temporarily increasing the tokens count.
        self._gen._size.tokens += reserve
        self._weights = None

    def __enter__(self):
        self._weights = [w if self._gen._size + self._min_sizes[i] <= self._gen._limit else 0 for i, w in enumerate(self._conditions)]
        if sum(self._weights) > 0:
            return self

        # Find alternative with the minimum depth and adapt token limit accordingly.
        min_size = min((self._min_sizes[i] for i, w in enumerate(self._conditions) if w > 0), key=lambda s: (s.depth, s.tokens))
        new_limit = self._gen._size + min_size
        if new_limit.depth > self._gen._limit.depth:
            logger.debug('max_depth must be temporarily updated from %s to %s', self._gen._limit.depth, new_limit.depth)
            self._gen._limit.depth = new_limit.depth
        if new_limit.tokens > self._gen._limit.tokens:
            logger.debug('max_tokens must be updated from %s to %s', self._gen._limit.tokens, new_limit.tokens)
            self._gen._limit.tokens = new_limit.tokens
        self._weights = [w if self._gen._size + self._min_sizes[i] <= self._gen._limit else 0 for i, w in enumerate(self._conditions)]
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Reset temporary size values.
        self._gen._limit.depth = self._orig_depth_limit
        self._gen._size.tokens -= self._reserve

    def __call__(self, node):
        return self._gen._model.choice(node, self._idx, self._weights)


class QuantifierContext:

    def __init__(self, gen, idx, start, stop, min_size, reserve):
        self._gen = gen
        self._idx = idx
        self._cnt = 0
        self._start = start
        self._stop = stop
        self._min_size = min_size
        self._reserve = reserve

    def __enter__(self):
        # Reserve token budget for the rest of the test case by temporarily increasing the tokens count.
        self._gen._size.tokens += self._reserve
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore the tokens value.
        self._gen._size.tokens -= self._reserve

    def __call__(self, node):
        if self._cnt < self._start:
            self._cnt += 1
            return True

        # Generate optional items if the current repeat count is between ``_start`` and ``_stop`` and
        # if size limits allows the generation and if the current model decides so, too.
        if (self._cnt < self._stop
                and self._gen._size + self._min_size <= self._gen._limit
                and self._gen._model.quantify(node, self._idx, self._cnt, self._start, self._stop)):
            self._cnt += 1
            return True

        return False


class Generator:
    """
    Base class of the generated Generators. Stores the decision model, the listeners,
    and additional internal state used during generation.
    """

    def __init__(self, *, model=None, listeners=None, limit=None):
        """
        :param Model model: Model object responsible for every decision during the generation.
               (default: :class:`DefaultModel`).
        :param list[Listener] listeners: Listeners that get notified whenever a
               rule is entered or exited.
        :param RuleSize limit: The limit on the depth of the trees and on the
               number of tokens (number of unlexer rule calls), i.e., it must
               be possible to finish generation from the selected node so that
               the overall depth and token count of the tree does not exceed
               these limits (default value: :attr:`RuleSize.max`).
        """
        self._model = model or DefaultModel()
        self._size = RuleSize()
        self._limit = limit or RuleSize.max
        self._listeners = listeners or []

    def _reserve(self, reserve, fn, *args, **kwargs):
        self._size.tokens += reserve
        fn(*args, **kwargs)
        self._size.tokens -= reserve

    def _enter_rule(self, node):
        for listener in self._listeners:
            listener.enter_rule(node)

    def _exit_rule(self, node):
        for listener in reversed(self._listeners):
            listener.exit_rule(node)

    @staticmethod
    def _charset(ranges):
        return tuple(itertools.chain.from_iterable(range(start, stop) for start, stop in ranges))
