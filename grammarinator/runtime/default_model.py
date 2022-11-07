# Copyright (c) 2020-2022 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random


class DefaultModel(object):

    def choice(self, node, idx, weights):
        # assert sum(weights) > 0, 'Sum of weights is zero.'
        return random.choices(range(len(weights)), weights=weights)[0]

    def quantify(self, node, idx, min, max):
        cnt = 0
        for _ in range(min):
            yield
            cnt += 1
        while cnt < max and bool(random.getrandbits(1)):
            yield
            cnt += 1

    def charset(self, node, idx, chars):
        return chr(random.choice(chars))
