# Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unparser is used by Custom.g4

from grammarinator.runtime import UnlexerRule, UnparserRuleContext

from CustomGenerator import CustomGenerator


class CustomSubclassGenerator(CustomGenerator):

    cnt: int = 0

    def tagname(self, parent=None):
        self.cnt += 1

        with UnparserRuleContext(self, 'tagname', parent) as rule:
            current = rule.current
            current += UnlexerRule(name='ID', src='customtag')
            return current

    def _custom_lexer_content(self):
        assert self.cnt > 0
        return 'custom content'
