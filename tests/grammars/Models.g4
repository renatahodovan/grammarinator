/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether DispatchingModel works as expected.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 --model {grammar}Generator.CustomModel -o {tmpdir}/{grammar}%d.txt

grammar Models;

@header {

from grammarinator.runtime import DispatchingModel


class CustomModel(DispatchingModel):

    def choice_start(self, node, idx, weights):
        # Enforce choosing the third alternative (`c`).
        return 2

    def quantify_start(self, node, idx, min, max):
        # Enforce to repeat 3 times.
        for i in range(3):
            yield

    def charset_C(self, node, idx, chars):
        # Enforce to choose `c` from the charset.
        return 'c'
}


start : (a | b | c)+ {assert str(current) == 'ccc', str(current)};
a : A ;
b : B ;
c : C ;

A : 'a' ;
B : 'b' ;
C : [a-z] ;
