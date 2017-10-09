# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unparser is used by Custom.g4

from grammarinator.runtime import *

from CustomUnparser import CustomUnparser


class CustomSubclassUnparser(CustomUnparser):

    def random_decision(self, *args, **kwargs):
        return False

    def tagname(self, *args, **kwargs):
        current = self.create_node(UnparserRule(name='tagname'))
        current += UnlexerRule(src='customtag')
        return current
