# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unparser is used by Custom.g4

from grammarinator.runtime import *

from CustomGenerator import CustomGenerator


class CustomSubclassGenerator(CustomGenerator):

    def tagname(self, parent=None):
        with UnparserRuleContext(gen=self, name='tagname', parent=parent) as current:
            UnlexerRule(src='customtag', parent=current)
            return current

    def _custom_lexer_content(self):
        return 'custom content'
