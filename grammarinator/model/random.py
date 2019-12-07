# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random


class RandomModel(object):

    def random_decision(self):
        return bool(random.getrandbits(1))

    def choice(self, choices):
        # assert sum(choices) > 0, 'Sum of choices is zero.'
        max_item = max(choices)
        choices = [i / max_item for i in choices]
        r = random.uniform(0, sum(choices))
        upto = 0
        for i, w in enumerate(choices):
            if upto + w >= r:
                return i
            upto += w
        raise AssertionError('Shouldn\'t get here.')

    def zero_or_one(self):
        if self.random_decision():
            yield

    def zero_or_more(self):
        while self.random_decision():
            yield

    def one_or_more(self):
        yield
        yield from self.zero_or_more()
