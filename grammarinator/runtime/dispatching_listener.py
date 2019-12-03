# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .default_listener import DefaultListener


class DispatchingListener(DefaultListener):

    def enter_rule(self, node):
        fn = 'enter_' + node.name
        if hasattr(self, fn):
            getattr(self, fn)(node)

    def exit_rule(self, node):
        fn = 'exit_' + node.name
        if hasattr(self, fn):
            getattr(self, fn)(node)
