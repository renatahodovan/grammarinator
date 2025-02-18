# Copyright (c) 2019-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom superclass is used by SuperClass.g4 and SuperClassOption.g4

from grammarinator.runtime import Generator, UnlexerRule


class SuperGenerator(Generator):

    def InheritedRule(self, parent=None):
        current = UnlexerRule(name='InheritedRule', src='I was inherited.')
        if parent:
            parent += current
        return current
