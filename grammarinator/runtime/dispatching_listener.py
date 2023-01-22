# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .default_listener import DefaultListener


class DispatchingListener(DefaultListener):
    """
    Subclass of :class:`DefaultListener` to make action definition more convenient.
    Subclassing ``DispatchingListener`` enables to define the enter and exit
    methods of a rule in the form of ``[enter|exit]_{rule_name}``.
    """

    def enter_rule(self, node):
        """
        Trampoline method calling the ``enter_{node.name}`` method of the subclassed listener, if it is defined.

        :param ~grammarinator.runtime.BaseRule node: Empty node that is about to have a subtree generated.
        """
        fn = 'enter_' + node.name
        if hasattr(self, fn):
            getattr(self, fn)(node)

    def exit_rule(self, node):
        """
        Trampoline method calling the ``exit_{node.name}`` method of the subclassed listener, if it is defined.

        :param ~grammarinator.runtime.BaseRule node: Node with its subtree just generated.
        """
        fn = 'exit_' + node.name
        if hasattr(self, fn):
            getattr(self, fn)(node)
