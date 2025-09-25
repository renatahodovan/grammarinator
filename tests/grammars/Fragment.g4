/*
 * Copyright (c) 2024-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether listeners see the correct names when lexer rules
 * refer to other lexer rules (usually, fragment rules).
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 1 --listener {grammar}Generator.{grammar}Listener -o {tmpdir}/{grammar}%d.txt

grammar Fragment;

@header {

from collections import Counter
from grammarinator.runtime import Listener


class FragmentListener(Listener):

    def __init__(self):
        self.cnt_enters = Counter()
        self.cnt_exits = Counter()

    def enter_rule(self, node):
        self.cnt_enters[node.name] += 1

    def exit_rule(self, node):
        self.cnt_exits[node.name] += 1
        if node.name == 'start':
            assert self.cnt_enters == Counter(start=1, A=1, B=1, C=1, D=1, E=1), self.cnt_enters
            assert self.cnt_exits == Counter(start=1, A=1, B=1, C=1, D=1, E=1), self.cnt_exits
}


start : A;
A : 'a' B ;
B : 'b' C ;
fragment C : 'c' D ;
fragment D : 'd' E ;
E : 'e' ;
