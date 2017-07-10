# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random
import string

from itertools import chain

from .tree import *


def printable_ranges(lower_bound, upper_bound):
    ranges = []
    range_start = None
    for c in range(lower_bound, upper_bound):
        if chr(c).isprintable():
            if range_start is None:
                range_start = c
        else:
            if range_start is not None:
                ranges.append((range_start, c))
                range_start = None

    if range_start is not None:
        ranges.append((range_start, upper_bound))
    return ranges


printable_unicode_ranges = printable_ranges(0x000000, 0x110000)
printable_unicode_chars = list(chain(*printable_unicode_ranges))
printable_ascii_ranges = printable_ranges(0x00, 0x80)


def range_diff(r1, r2):
    s1, e1 = r1
    s2, e2 = r2
    endpoints = sorted((s1, s2, e1, e2))
    result = []
    if endpoints[0] == s1:
        result.append((endpoints[0], endpoints[1]))
    if endpoints[3] == e1:
        result.append((endpoints[2], endpoints[3]))
    return result


def multirange_diff(r1_list, r2_list):
    for r2 in r2_list:
        r1_list = list(chain(*[range_diff(r1, r2) for r1 in r1_list]))
    return r1_list


class Grammarinator(object):

    def __init__(self, *, max_cnt=8000):
        self.root = None
        self.node_cnt = 0
        self.max_cnt = max_cnt
        self.options = dict()

    def set_options(self):
        pass

    def create_node(self, node):
        self.root = self.root or node
        self.node_cnt += 1
        return node

    def random_decision(self, *, max_depth=float('inf')):
        return bool(random.getrandbits(1))

    def choice(self, choices):
        #assert sum(choices) > 0, 'Sum of choices is zero.'
        r = random.uniform(0, sum(choices))
        upto = 0
        for i, w in enumerate(choices):
            if upto + w >= r:
                return i
            upto += w
        assert False, 'Shouldn\'t get here.'

    def depth_limited_weights(self, weights, min_depths, max_depth):
        for i, w in enumerate(weights):
            # Disable options that cannot be finished within the given max_depth.
            if min_depths[i] > max_depth:
                weights[i] = 0
        return weights

    def zero_or_one(self, *, max_depth=float('inf')):
        if self.random_decision(max_depth=max_depth):
            yield
        raise StopIteration

    def zero_or_more(self, *, max_depth=float('inf')):
        while self.random_decision(max_depth=max_depth):
            yield
        raise StopIteration

    def one_or_more(self, *, max_depth=float('inf')):
        yield
        yield from self.zero_or_more(max_depth=max_depth)

    def char_from_list(self, options):
        return chr(random.choice(options))

    def any_ascii_char(self):
        return random.choice(string.printable)

    def any_unicode_char(self):
        return self.char_from_list(printable_unicode_chars)

    def any_ascii_letter(self):
        return random.choice(string.ascii_letters)

    def any_char(self):
        if 'dot' in self.options:
            return getattr(self, self.options['dot'])()
        return self.any_ascii_char()

    def obj_join(self, lst, item):
        result = [item] * (len(lst) * 2 - 1)
        result[0::2] = lst
        return result

    # TODO: move to specific fuzzers
    def choose_multiple(self, options, *, max_depth=float('inf'), interval=None, repeat=True, glue=' '):
        if not interval and not repeat:
            interval = range(1, len(options))

        result = []
        for _ in range(random.choice(interval)) if interval else self.one_or_more():
            choice = random.choice(options)
            if not repeat:
                options.remove(choice)
            result.append(choice(max_depth=max_depth) if callable(choice) else UnlexerRule(src=choice))
        return self.obj_join(result, UnlexerRule(src=glue))

    def repeat(self, rule, *, max_depth=float('inf'), interval=None, glue=' '):
        if not interval:
            interval = self.one_or_more(max_depth=max_depth)

        result = []
        for _ in interval:
            result.append(rule(max_depth=max_depth) if callable(rule) else rule)
        return self.obj_join(result, UnlexerRule(src=glue))
