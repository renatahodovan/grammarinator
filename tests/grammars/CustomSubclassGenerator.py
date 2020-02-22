# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unparser is used by Custom.g4

from grammarinator.runtime import *

from CustomGenerator import CustomGenerator


class CustomSubclassGenerator(CustomGenerator):

    def random_decision(self, *args, **kwargs):
        return False

    def tagname(self, *args, **kwargs):
        current = self.create_node(UnparserRule(name='tagname'))
        current += UnlexerRule(src='customtag')
        return current

    def _custom_lexer_content(self):
        return UnlexerRule(src='custom content')
