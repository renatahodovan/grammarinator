# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .tree import *


def simple_space_serializer(root):

    def _walk(node):
        nonlocal src
        for child in node.children:
            _walk(child)

            if isinstance(node, UnparserRule):
                src += ' '

        if isinstance(node, UnlexerRule) and node.src:
            src += node.src

    src = ''
    _walk(root)
    return src
