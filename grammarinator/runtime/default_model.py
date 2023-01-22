# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random


class DefaultModel(object):
    """
    Default model implementation responsible for making decisions at alternations,
    quantifiers and charsets:

      - At alternations, the decision is solely based upon the provided weights.
      - At quantifiers, after generating the minimum expected items, every further
        expansion happens based on a random binary decision.
      - At charsets, a single character is choosen randomly from a set of possible
        options.
    """

    def choice(self, node, idx, weights):
        """
        Method called by the generated fuzzer class to choose an alternative
        from an alternation.

        :param ~grammarinator.runtime.BaseRule node: Rule node object containing the alternation to choose an alternative from.
        :param int idx: Index of the alternation inside the current rule.
        :param list[float] weights: Weights assigned to alternatives of the selected alternation.
        """
        # assert sum(weights) > 0, 'Sum of weights is zero.'
        return random.choices(range(len(weights)), weights=weights)[0]

    def quantify(self, node, idx, min, max):
        """
        Method called by the generated fuzzer class to guide the loop of subtree quantification.
        This is a generator method in pythonic sense, i.e., it should be used within a loop or with next(), etc.

        :param BaseRule node: Rule node object containing the quantified subtree.
        :param int idx: Index of the quantified subtree inside the current rule.
        :param int min: Lower boundary of the quantification range.
        :param int max: Upper boundary of the quantification range.
        """
        cnt = 0
        for _ in range(min):
            yield
            cnt += 1
        while cnt < max and bool(random.getrandbits(1)):
            yield
            cnt += 1

    def charset(self, node, idx, chars):
        """
        Method to choose character from a charset.

        :param BaseRule node: Rule node object containing the charset.
        :param int idx: Index of the charset inside the current rule.
        :param list[str] chars: List of characters to choose a single character from.
        """
        return chr(random.choice(chars))
