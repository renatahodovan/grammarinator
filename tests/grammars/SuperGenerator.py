# Copyright (c) 2019-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom superclass is used by SuperClass.g4 and SuperClassOption.g4

from grammarinator.runtime import *


class SuperGenerator(Generator):

    def inheritedRule(self, parent=None):
        return UnlexerRule(src='I was inherited.', parent=parent)
