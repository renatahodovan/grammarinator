/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
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
// TEST-GENERATE: Custom{grammar}Generator.Custom{grammar}Generator -r start -j 1 -o {tmpdir}/{grammar}%d.txt


grammar ImplicitLiteral;

@members {
def __init__(self, *, model=None, listeners=None, max_depth=inf):
    super().__init__(model=model, listeners=listeners, max_depth=max_depth)
    self.hello_called = False
}


start : 'hello' {assert self.hello_called, "Implicit lexer rule was not called."};
HELLO : 'hello' ;
