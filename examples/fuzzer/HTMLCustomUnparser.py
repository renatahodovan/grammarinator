# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import random

from os.path import dirname, join

from grammarinator.runtime import *
from HTMLUnparser import HTMLUnparser


with open(join(dirname(__file__), 'html.json')) as f:
    tags = json.load(f)


class HTMLCustomUnparser(HTMLUnparser):

    attr_stack = []
    tag_stack = []
    tags = set()

    def __init__(self, lexer):
        super(HTMLCustomUnparser, self).__init__(lexer)
        self.tag_names = list(tags.keys())

    # Override the original random_decision implementation in a way to increase the number of generated nodes.
    def random_decision(self, *, max_depth=float('inf')):
        # Playing with size.
        if self.node_cnt < self.max_cnt // 4:
            return random.randint(0, 1000) > 100
        return random.randint(0, 1000) < 400

    # Customize the function generated from the htmlTagName parser rule to produce valid tag names.
    def htmlTagName(self, *, max_depth=float('inf')):
        current = self.create_node(UnparserRule(name='htmlTagName'))
        name = random.choice(tags[self.tag_stack[-1]]['children'] or self.tag_names if self.tag_stack else self.tag_names)
        self.tag_stack.append(name)
        current += UnlexerRule(src=name)
        self.tag_stack.append(name)
        return current

    # Customize the function generated from the htmlAttributeName parser rule to produce valid attribute names.
    def htmlAttributeName(self, *, max_depth=float('inf')):
        current = self.create_node(UnparserRule(name='htmlAttributeName'))
        name = random.choice(list(tags[self.tag_stack[-1]]['attributes'].keys()) or ['""'])
        self.attr_stack.append(name)
        current += UnlexerRule(src=name)
        return current

    # Customize the function generated from the htmlAttributeValue parser rule to produce valid attribute values
    # to the current tag and attribute name.
    def htmlAttributeValue(self, *, max_depth=float('inf')):
        current = self.create_node(UnparserRule(name='htmlAttributeValue'))
        current += UnlexerRule(src=random.choice(tags[self.tag_stack[-1]]['attributes'].get(self.attr_stack.pop(), ['""']) or ['""']))
        return current

    def endOfHtmlElement(self, *, max_depth=float('inf')):
        self.tag_stack.pop()
