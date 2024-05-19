# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from .default_model import DefaultModel
from .rule import RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantified, UnparserRuleQuantifier

logger = logging.getLogger(__name__)


class Context:

    def __init__(self, node):
        self.node = node

    def __enter__(self):
        # Returns self. Effectively a no-op. Can be safely overridden by
        # subclasses without calling super().__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # A no-op. Can be safely overridden by subclasses without calling
        # super().__exit__(exc_type, exc_val, exc_tb)
        pass


class RuleContext(Context):
    # Context manager wrapping rule generations. It is responsible for
    # keeping track of the value of `max_depth` and for transitively calling the
    # enter and exit methods of the registered listeners.

    def __init__(self, gen, node):
        super().__init__(node)
        self.gen = gen
        self.ctx = self

    @property
    def current(self):
        return self.ctx.node

    def __enter__(self):
        # Increment current depth by 1 before entering the next level.
        self.gen._size.depth += 1
        self.gen._enter_rule(self.node)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.gen._exit_rule(self.node)
        # Decrementing current depth after finishing a rule.
        self.gen._size.depth -= 1


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
            self._start_depth = self.gen._size.depth

    def __enter__(self):
        super().__enter__()
        # Increment token count with the current token.
        self.gen._size.tokens += 1
        # Keep track of the depth and token count of lexer rules, since these
        # values cannot be calculated from the output tree.
        self.node.size.tokens += 1
        self.node.size.depth = max(self.node.size.depth, self.gen._size.depth)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        if self._start_depth is not None:
            self.node.size.depth -= self._start_depth


class UnparserRuleContext(RuleContext):
    # Subclass of :class:`RuleContext` handling unparser rules.

    def __init__(self, gen, name, parent=None):
        node = UnparserRule(name=name)
        if parent:
            parent += node
        super().__init__(gen, node)


class SubRuleContext(Context):

    def __init__(self, rule, node=None):
        super().__init__(node or rule.current)
        self._rule = rule
        self._prev_ctx = rule.ctx
        if node:
            self._prev_ctx.node += node

    def __enter__(self):
        self._rule.ctx = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rule.ctx = self._prev_ctx


class AlternationContext(SubRuleContext):
    # Context manager wrapping alternations. It is responsible for filtering
    # the alternatives available within the maximum depth, token size and
    # decisions. Otherwise, if nothing is available (possibly due to some
    # custom predicates or rule definitions or contradicting size limits),
    # then it temporarily raises the maximum size to the minimum value
    # required to finish the generation.

    def __init__(self, rule, idx, min_sizes, reserve, conditions):
        super().__init__(rule)  # No node created here, defer it to __enter__ when all information is available
        self.idx = idx
        self._min_sizes = min_sizes
        self._reserve = reserve  # Minimum number of remaining tokens needed by the right siblings.
        self._conditions = conditions  # Boolean values enabling or disabling the certain alternatives.
        self._orig_depth_limit = rule.gen._limit.depth
        self._weights = None
        self._choice = None

    def __enter__(self):
        super().__enter__()

        # Reserve token budget for the rest of the test case by temporarily increasing the tokens count.
        gen = self._rule.gen
        gen._size.tokens += self._reserve

        self._weights = [w if gen._size + self._min_sizes[i] <= gen._limit else 0 for i, w in enumerate(self._conditions)]
        if sum(self._weights) == 0:
            # Find alternative with the minimum depth and adapt token limit accordingly.
            min_size = min((self._min_sizes[i] for i, w in enumerate(self._conditions) if w > 0), key=lambda s: (s.depth, s.tokens))
            new_limit = gen._size + min_size
            if new_limit.depth > gen._limit.depth:
                logger.debug('max_depth must be temporarily updated from %s to %s', gen._limit.depth, new_limit.depth)
                gen._limit.depth = new_limit.depth
            if new_limit.tokens > gen._limit.tokens:
                logger.debug('max_tokens must be updated from %s to %s', gen._limit.tokens, new_limit.tokens)
                gen._limit.tokens = new_limit.tokens
            self._weights = [w if gen._size + self._min_sizes[i] <= gen._limit else 0 for i, w in enumerate(self._conditions)]

        # Make the choice and store the result for the __call__, and create the node.
        self._choice = self._rule.gen._model.choice(self._rule.node, self.idx, self._weights)
        if not isinstance(self._rule.node, UnlexerRule):
            self.node = UnparserRuleAlternative(alt_idx=self.idx, idx=self._choice)
            self._prev_ctx.node += self.node

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        # Reset temporary size values.
        gen = self._rule.gen
        gen._limit.depth = self._orig_depth_limit
        gen._size.tokens -= self._reserve

    def __call__(self):
        return self._choice


class QuantifierContext(SubRuleContext):

    def __init__(self, rule, idx, start, stop, min_size, reserve):
        super().__init__(rule, UnparserRuleQuantifier(idx=idx, start=start, stop=stop) if not isinstance(rule.node, UnlexerRule) else None)
        self.idx = idx
        self._start = start
        self._stop = stop
        self._min_size = min_size
        self._reserve = reserve
        self._cnt = 0

    def __enter__(self):
        super().__enter__()
        # Reserve token budget for the rest of the test case by temporarily increasing the tokens count.
        self._rule.gen._size.tokens += self._reserve
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        # Restore the tokens value.
        self._rule.gen._size.tokens -= self._reserve

    def __call__(self):
        if self._cnt < self._start:
            self._cnt += 1
            return True

        # Generate optional items if the current repeat count is between ``_start`` and ``_stop`` and
        # if size limits allows the generation and if the current model decides so, too.
        gen = self._rule.gen
        if (self._cnt < self._stop
                and gen._size + self._min_size <= gen._limit
                and gen._model.quantify(self._rule.node, self.idx, self._cnt, self._start, self._stop)):
            self._cnt += 1
            return True

        return False


class QuantifiedContext(SubRuleContext):

    def __init__(self, rule):
        super().__init__(rule, UnparserRuleQuantified() if not isinstance(rule.node, UnlexerRule) else None)


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
               these limits (default: :class:`RuleSize`. ``max``).
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
