# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class Model:
    """
    Abstract base class of models that make decisions for generators at
    alternations, quantifiers, and charsets.
    """

    def choice(self, node, idx, weights):
        """
        Choose an alternative from an alternation.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule node: The current node. Its ``name``
            field identifies the corresponding grammar rule, which contains the
            alternation to choose an alternative from.
        :param int idx: Index of the alternation inside the current rule.
        :param list[float] weights: Weights assigned to alternatives of the
            selected alternation.
        :return: The index of the chosen alternative.
        :rtype: int
        """
        raise NotImplementedError()

    def quantify(self, node, idx, cnt, start, stop):
        """
        Guide the loop of subtree quantification. This has to make a binary
        decision to tell whether to enable the next iteration or stop the loop.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule node: The current node. Its ``name``
            field identifies the corresponding grammar rule, which contains the
            quantified subtree.
        :param int idx: Index of the quantified subtree inside the current rule.
        :param int cnt: Number of the already generated subtrees, guaranteed
            to be between ``start`` (inclusive) and ``stop`` (exclusive).
        :param int start: Lower bound of the quantification range.
        :param int stop: Upper bound of the quantification range.
        :return: Boolean value enabling the next iteration or stopping it.
        :rtype: bool
        """
        raise NotImplementedError()

    def charset(self, node, idx, chars):
        """
        Choose a character from a charset.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule node: The current node. Its ``name``
            field identifies the corresponding grammar rule, which contains the
            charset.
        :param int idx: Index of the charset inside the current rule.
        :param list[str] chars: List of characters to choose a single character
            from.
        :return: The chosen character.
        :rtype: str
        """
        raise NotImplementedError()
