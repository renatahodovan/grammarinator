# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random

from .model import Model


class DefaultModel(Model):
    """
    Default decision model implementation.
    """

    def choice(self, node, idx, weights):
        """
        The decision is solely based upon the provided ``weights``.

        Parameters ``node`` and ``idx`` are unused.
        """
        # assert sum(weights) > 0, 'Sum of weights is zero.'
        return random.choices(range(len(weights)), weights=weights)[0]

    def quantify(self, node, idx, cnt, min, max):
        """
        After generating the minimum expected items (``min``) and before
        reaching the maximum expected items (``max``), quantify decides about
        the expansion of the optional items based on a random binary decision.

        Parameters ``node``, ``idx``, ``cnt``, ``min`` and ``max`` are unused.
        """
        return bool(random.getrandbits(1))

    def charset(self, node, idx, chars):
        """
        A single character is chosen randomly from the set of possible options
        (``chars``).

        Parameters ``node`` and ``idx`` are unused.
        """
        return chr(random.choice(chars))
