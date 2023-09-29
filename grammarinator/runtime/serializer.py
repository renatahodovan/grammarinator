# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .rule import UnparserRule


def simple_space_serializer(root):
    """
    Simple serializer concatenating the children of :class:`UnparserRule` s with a single
    space, while the children of :class:`UnlexerRule` s (tokens) are glued without any character.

    :param Rule root: The root node of the tree or subtree to serialize.
    :return: The serialized tree as string.
    :rtype: str
    """

    def _walk(node):
        if isinstance(node, UnparserRule):
            for child in node.children:
                _walk(child)
        else:
            tokens.append(node.src)

    tokens = []
    _walk(root)
    return ' '.join(tokens)
