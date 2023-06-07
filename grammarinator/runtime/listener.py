# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class Listener(object):
    """
    Base class of listeners that get notified by generators whenever a rule is
    entered or exited. which needs to be subclassed.
    """
    # Note: Generators use grammarinator.runtime.RuleContext context managers
    # when generating rules. RuleContext.__enter__ is responsible for calling
    # enter_rule of listeners, while RuleContext.__exit__ calls exit_rule.

    def enter_rule(self, node):
        """
        Actions to take when a rule is entered, i.e., before creating the
        derivation of ``node``.

        No-op by default.

        :param ~grammarinator.runtime.BaseRule node: Empty node (it has no
            children yet, but ``node.name`` and ``node.parent`` are already
            valid) that is about to have a subtree generated.
        """

    def exit_rule(self, node):
        """
        Actions to take when a rule is exited, i.e., after creating the
        derivation of ``node``.

        No-op by default.

        :param ~grammarinator.runtime.BaseRule node: Node with its subtree just
            generated.
        """
