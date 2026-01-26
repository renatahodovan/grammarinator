# Copyright (c) 2023-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .rule import Rule


class Model:
    """
    Abstract base class of models that make decisions for generators at
    alternations, quantifiers, and charsets.
    """

    def choice(self, node: Rule, idx: int, weights: list[float]) -> int:
        """
        Choose an alternative from an alternation.

        Raises :exc:`NotImplementedError` by default.

        :param node: The current node. Its ``name`` field identifies the
            corresponding grammar rule, which contains the alternation to choose
            an alternative from.
        :param idx: Index of the alternation inside the current rule.
        :param weights: Weights assigned to alternatives of the selected
            alternation.
        :return: The index of the chosen alternative.
        """
        raise NotImplementedError()

    def quantify(self, node: Rule, idx: int, cnt: int, start: int, stop: int | float, prob: float = 0.5) -> bool:
        """
        Guide the loop of subtree quantification. This has to make a binary
        decision to tell whether to enable the next iteration or stop the loop.

        Raises :exc:`NotImplementedError` by default.

        :param node: The current node. Its ``name`` field identifies the
            corresponding grammar rule, which contains the quantified subtree.
        :param idx: Index of the quantified subtree inside the current rule.
        :param cnt: Number of the already generated subtrees, guaranteed to be
            between ``start`` (inclusive) and ``stop`` (exclusive).
        :param start: Lower bound of the quantification range.
        :param stop: Upper bound of the quantification range.
        :param prob: Predefined probability of enabling the next iteration
            (between 0 and 1).
        :return: Boolean value enabling the next iteration or stopping it.
        """
        raise NotImplementedError()

    def charset(self, node: Rule, idx: int, chars: tuple[int, ...]) -> str:
        """
        Choose a character from a charset.

        Raises :exc:`NotImplementedError` by default.

        :param node: The current node. Its ``name`` field identifies the
            corresponding grammar rule, which contains the charset.
        :param idx: Index of the charset inside the current rule.
        :param chars: List of character codes (Unicode code points as
            integers) to choose a single character from.
        :return: The chosen character.
        """
        raise NotImplementedError()
