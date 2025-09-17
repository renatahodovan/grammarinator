/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * Tests handling of implicit literals in parser rules.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 --listener {grammar}Generator.{grammar}Listener -o {tmpdir}/{grammar}%d.txt

grammar ImplicitLiteral;

@header {

from grammarinator.runtime import DispatchingListener


class ImplicitLiteralListener(DispatchingListener):

    def __init__(self):
        self.hello_called = False

    def exit_HELLO(self, node):
        self.hello_called = True

    def exit_start(self, node):
        assert self.hello_called, "Implicit lexer rule was not called."
}


start : 'hello';
HELLO : 'hello';
