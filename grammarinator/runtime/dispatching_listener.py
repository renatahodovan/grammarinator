# Copyright (c) 2020-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .listener import Listener
from .rule import Rule


class DispatchingListener(Listener):
    """
    Base class of custom listeners that aim to override the enter and exit
    actions for specific rules. Subclassing ``DispatchingListener`` enables to
    define the enter and exit methods of a rule in the form of
    ``[enter|exit]_{rule_name}``.
    """

    def enter_rule(self, node: Rule) -> None:
        """
        Trampoline to the ``enter_{node.name}`` method of the subclassed listener, if it is defined.
        """
        fn = 'enter_' + node.name
        if hasattr(self, fn):
            getattr(self, fn)(node)

    def exit_rule(self, node: Rule) -> None:
        """
        Trampoline to the ``exit_{node.name}`` method of the subclassed listener, if it is defined.
        """
        fn = 'exit_' + node.name
        if hasattr(self, fn):
            getattr(self, fn)(node)
