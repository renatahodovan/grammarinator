# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unparser is used by Custom.g4

from grammarinator.runtime import UnlexerRule, UnparserRuleContext

from CustomGenerator import CustomGenerator


class CustomSubclassGenerator(CustomGenerator):

    def tagname(self, parent=None):
        with UnparserRuleContext(self, 'tagname', parent) as rule:
            current = rule.current
            current += UnlexerRule(src='customtag')
            return current

    def _custom_lexer_content(self):
        return 'custom content'
