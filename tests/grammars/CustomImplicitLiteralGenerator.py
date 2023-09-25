# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unparser is used by ImplicitLiteral.g4

from ImplicitLiteralGenerator import ImplicitLiteralGenerator


class CustomImplicitLiteralGenerator(ImplicitLiteralGenerator):

    def HELLO(self, parent=None):
        super().HELLO(parent=parent)
        self.hello_called = True
