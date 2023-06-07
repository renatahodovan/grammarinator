# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class Model(object):
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

    def quantify(self, node, idx, min, max):
        """
        Guide the loop of subtree quantification. This has to be a generator
        method in pythonic sense, i.e., it will be used in loops and it should
        ``yield`` as many times as the loop should iterate.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule node: The current node. Its ``name``
            field identifies the corresponding grammar rule, which contains the
            quantified subtree.
        :param int idx: Index of the quantified subtree inside the current rule.
        :param int min: Lower bound of the quantification range.
        :param int max: Upper bound of the quantification range.
        :return: The value yielded is never used, but the number this generator
            method yields is relevant (expected to be in the ``min``-``max``
            range, inclusive).
        :rtype: None
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
