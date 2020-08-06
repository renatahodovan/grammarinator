# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import random
import string

from itertools import chain
from math import inf

from ..model import DefaultModel


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
    return [range(*r1) for r1 in r1_list]


def depthcontrol(fn):
    def controlled_fn(obj, *args, **kwargs):
        obj.max_depth -= 1
        try:
            result = fn(obj, *args, **kwargs)
        finally:
            obj.max_depth += 1
        return result

    controlled_fn.__name__ = fn.__name__
    return controlled_fn


class Generator(object):

    def __init__(self, *, model=None, max_depth=inf):
        self.model = model or DefaultModel()
        self.max_depth = max_depth
        self.listeners = []

    @staticmethod
    def char_from_list(options):
        return chr(random.choice(options))

    @staticmethod
    def any_ascii_char():
        return random.choice(string.printable)

    @staticmethod
    def any_unicode_char():
        return Generator.char_from_list(printable_unicode_chars)

    @staticmethod
    def any_ascii_letter():
        return random.choice(string.ascii_letters)

    any_char = any_ascii_char

    def enter_rule(self, node):
        for listener in self.listeners:
            listener.enter_rule(node)

    def exit_rule(self, node):
        for listener in reversed(self.listeners):
            listener.exit_rule(node)
