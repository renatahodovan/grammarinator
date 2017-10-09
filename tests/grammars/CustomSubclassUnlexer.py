# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

# This custom unlexer is used by Custom.g4

from grammarinator.runtime import *

from CustomUnlexer import CustomUnlexer


class CustomSubclassUnlexer(CustomUnlexer):

    def _custom_lexer_content(self):
        return UnlexerRule(src='custom content')
