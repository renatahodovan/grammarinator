# Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from __future__ import annotations

import itertools
import logging

from collections.abc import Callable
from typing import ClassVar, Optional, Union

from .default_model import DefaultModel
from .listener import Listener
from .model import Model
from .rule import ParentRule, Rule, RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantified, UnparserRuleQuantifier

logger = logging.getLogger(__name__)


class Context:

    __slots__ = ('node',)

    def __init__(self, node: Rule) -> None:
        self.node: Rule = node

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

    __slots__ = ('gen', 'ctx')

    def __init__(self, gen: Generator, node: Rule) -> None:
        super().__init__(node)
        self.gen: Generator = gen
        self.ctx: Context = self

    @property
    def current(self) -> Rule:
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

    __slots__ = ('_start_depth', '_parent_name', '_name')

    def __init__(self, gen: Generator, name: str, parent: Optional[Union[UnlexerRule, ParentRule]] = None, immutable: bool = False) -> None:
        if isinstance(parent, UnlexerRule):
            # If parent node is also an UnlexerRule then this is a sub-rule and
            # actually no child node is created, but the parent is kept as the
            # current node
            super().__init__(gen, parent)
            self._start_depth: Optional[float] = None
            # So, save the name of the parent node and also that of the sub-rule
            self._parent_name: Optional[str] = parent.name
            self._name: Optional[str] = name
        else:
            node = UnlexerRule(name=name, immutable=immutable)
            if parent:
                parent += node
            super().__init__(gen, node)
            self._start_depth = self.gen._size.depth
            self._parent_name = None
            self._name = None

    def __enter__(self):
        # When entering a sub-rule, rename the current node to reflect the name
        # of the sub-rule
        if self._name is not None and self._parent_name is not None:
            self.node.name = self._name
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
        # When exiting a sub-rule, change the name of the current node back to
        # that of the parent
        if self._name is not None and self._parent_name is not None:
            self.node.name = self._parent_name


class UnparserRuleContext(RuleContext):
    # Subclass of :class:`RuleContext` handling unparser rules.

    def __init__(self, gen: Generator, name: str, parent: Optional[ParentRule] = None) -> None:
        node = UnparserRule(name=name)
        if parent:
            parent += node
        super().__init__(gen, node)


class SubRuleContext(Context):

    __slots__ = ('_rule', '_prev_ctx')

    def __init__(self, rule: RuleContext, node: Optional[Rule] = None) -> None:
        super().__init__(node or rule.current)
        self._rule: RuleContext = rule
        self._prev_ctx: Context = rule.ctx
        if node:
            assert isinstance(self._prev_ctx.node, ParentRule)
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

    __slots__ = ('idx', '_min_sizes', '_reserve', '_conditions', '_orig_depth_limit', '_weights', '_choice')

    def __init__(self, rule: RuleContext, idx: int, min_sizes: tuple[RuleSize, ...], reserve: int, conditions: tuple[float, ...]) -> None:
        super().__init__(rule)  # No node created here, defer it to __enter__ when all information is available
        self.idx: int = idx
        self._min_sizes: tuple[RuleSize, ...] = min_sizes
        self._reserve: int = reserve  # Minimum number of remaining tokens needed by the right siblings.
        self._conditions: tuple[float, ...] = conditions  # Boolean values enabling or disabling the certain alternatives.
        self._orig_depth_limit: float = rule.gen._limit.depth
        self._weights: Optional[list[float]] = None
        self._choice: Optional[int] = None

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

    def __call__(self) -> int:
        assert self._choice is not None, 'AlternationContext.__enter__() must be called before __call__()!'
        return self._choice


class QuantifierContext(SubRuleContext):

    __slots__ = ('idx', '_start', '_stop', '_min_size', '_reserve', '_cnt')

    def __init__(self, rule: RuleContext, idx: int, start: int, stop: Union[int, float], min_size: RuleSize, reserve: int) -> None:
        super().__init__(rule, UnparserRuleQuantifier(idx=idx, start=start, stop=stop) if not isinstance(rule.node, UnlexerRule) else None)
        self.idx: int = idx
        self._start: int = start
        self._stop: Union[int, float] = stop
        self._min_size: RuleSize = min_size
        self._reserve: int = reserve
        self._cnt: int = 0

    def __enter__(self):
        super().__enter__()
        # Reserve token budget for the rest of the test case by temporarily increasing the tokens count.
        self._rule.gen._size.tokens += self._reserve
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)
        # Restore the tokens value.
        self._rule.gen._size.tokens -= self._reserve

    def __call__(self) -> bool:
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

    def __init__(self, rule: RuleContext) -> None:
        super().__init__(rule, UnparserRuleQuantified() if not isinstance(rule.node, UnlexerRule) else None)


class Generator:
    """
    Base class of the generated Generators. Stores the decision model, the listeners,
    and additional internal state used during generation.
    """
    _rule_sizes: ClassVar[dict[str, RuleSize]]  #: Sizes of the rules, used to determine the minimum size of the generated trees. Generated into the generator subclasses by processor.
    _alt_sizes: ClassVar[tuple[tuple[RuleSize, ...], ...]]  #: Sizes of the alternatives of the rules, used to determine the minimum size of the generated trees. Generated into the generator subclasses by processor.
    _quant_sizes: ClassVar[tuple[RuleSize, ...]]  #: Sizes of the quantifiers of the rules, used to determine the minimum size of the generated trees. Generated into the generator subclasses by processor.
    _default_rule: ClassVar[Callable]  #: Reference to the default rule to start the generation with.

    def __init__(self, *, model: Optional[Model] = None, listeners: Optional[list[Listener]] = None, limit: Optional[RuleSize] = None) -> None:
        """
        :param model: Model object responsible for every decision during the
            generation. (default: :class:`DefaultModel`).
        :param listeners: Listeners that get notified whenever a rule is entered
            or exited.
        :param limit: The limit on the depth of the trees and on the number of
            tokens (number of unlexer rule calls), i.e., it must be possible to
            finish generation from the selected node so that the overall depth
            and token count of the tree does not exceed these limits (default:
            :class:`RuleSize`. ``max``).
        """
        self._model: Model = model or DefaultModel()
        self._size: RuleSize = RuleSize()  # The current size of the generated tree, i.e., the number of tokens and the depth.
        self._limit: RuleSize = limit or RuleSize.max
        self._listeners: list[Listener] = listeners or []

    def _reserve(self, reserve: int, fn: Callable[[Optional[ParentRule]], Rule], *args, **kwargs) -> None:
        self._size.tokens += reserve
        fn(*args, **kwargs)
        self._size.tokens -= reserve

    def _enter_rule(self, node: Rule) -> None:
        for listener in self._listeners:
            listener.enter_rule(node)

    def _exit_rule(self, node: Rule) -> None:
        for listener in reversed(self._listeners):
            listener.exit_rule(node)

    @staticmethod
    def _charset(ranges: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
        return tuple(itertools.chain.from_iterable(range(start, stop) for start, stop in ranges))
