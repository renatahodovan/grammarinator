# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random


class DefaultModel(object):

    def choice(self, node, idx, choices):
        # assert sum(choices) > 0, 'Sum of choices is zero.'
        max_item = max(choices)
        choices = [w / max_item for w in choices]
        r = random.uniform(0, sum(choices))
        upto = 0
        for i, w in enumerate(choices):
            if upto + w >= r:
                return i
            upto += w
        raise AssertionError('Shouldn\'t get here.')

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
