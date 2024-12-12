# Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .rule import Rule


def simple_space_serializer(root: Rule) -> str:
    """
    Simple serializer concatenating the children of :class:`UnparserRule` s with
    a single space.

    :param root: The root node of the tree or subtree to serialize.
    :return: The serialized tree as string.
    """
    return ' '.join(root.tokens())
