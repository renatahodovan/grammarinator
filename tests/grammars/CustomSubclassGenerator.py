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

    def tagname(self, parent=None):
        current = UnparserRule(name='tagname', parent=parent)
        UnlexerRule(src='customtag', parent=current)
        return current

    def _custom_lexer_content(self, parent=None):
        return UnlexerRule(src='custom content', parent=parent)
