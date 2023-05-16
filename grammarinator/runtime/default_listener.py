# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class DefaultListener(object):
    """
    Default implementation of a listener which needs to be subclassed.
    It defines the :meth:`enter_rule` and :meth:`exit_rule` methods that are
    executed whenever a rule is entered or exited, respectively.
    """
    # Note: Generators use grammarinator.runtime.RuleContext context managers
    # when generating rules. RuleContext.__enter__ is responsible for calling
    # enter_rule of listeners, while RuleContext.__exit__ calls exit_rule.

    def enter_rule(self, node):
        """
        Defines the actions to be taken before creating the derivation of ``node``. No-op by default.

        :param ~grammarinator.runtime.BaseRule node: Empty node (it has no children yet,
               but ``node.name`` and ``node.parent`` are already valid) that is about to have a subtree generated.
        """

    def exit_rule(self, node):
        """
        Defines the actions to be taken after creating the derivation of ``node``. No-op by default.

        :param ~grammarinator.runtime.BaseRule node: Node with its subtree just generated.
        """
