# Copyright (c) 2020-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random

from .model import Model
from .rule import Rule


class DefaultModel(Model):
    """
    Default decision model implementation.
    """

    def choice(self, node: Rule, idx: int, weights: list[float]) -> int:
        """
        The decision is solely based upon the provided ``weights``.

        Parameters ``node`` and ``idx`` are unused.
        """
        # assert sum(weights) > 0, 'Sum of weights is zero.'
        return random.choices(range(len(weights)), weights=weights)[0]

    def quantify(self, node: Rule, idx: int, cnt: int, start: int, stop: int | float) -> bool:
        """
        After generating the minimum expected items (``start``) and before
        reaching the maximum expected items (``stop``), quantify decides about
        the expansion of the optional items based on a random binary decision.

        Parameters ``node``, ``idx``, ``cnt``, ``start``, and ``stop`` are
        unused.
        """
        return bool(random.getrandbits(1))

    def charset(self, node: Rule, idx: int, chars: tuple[int, ...]) -> str:
        """
        A single character is chosen randomly from the set of possible options
        (``chars``).

        Parameters ``node`` and ``idx`` are unused.
        """
        return chr(random.choice(chars))
