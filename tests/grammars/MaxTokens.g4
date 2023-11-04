/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the maximum token restriction is respected
 * by both alternations and quantifiers.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -m {grammar}Generator.CustomGreedyModel -j 1 -o {tmpdir}/{grammar}%d.txt --max-tokens 7

grammar MaxTokens;

@header {
from grammarinator.runtime import DispatchingModel

class CustomGreedyModel(DispatchingModel):

    def quantify_start(self, node, idx, cnt, min, max):
        return True
}

start : a b+ c {assert str(current) in ['aaabbbc', 'aaaabbc'], str(current)};
a : A A A | A A A A;
b : B ;
c : C ;
A : 'a' ;
B : 'b' ;
C : 'c' ;
