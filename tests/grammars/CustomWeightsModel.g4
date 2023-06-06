/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether CustomWeightsModel works as expected.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 --weights custom_weights.json -o {tmpdir}/{grammar}S%d.txt
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 2 -n 5 --weights custom_weights.json -o {tmpdir}/{grammar}M%d.txt

grammar CustomWeightsModel;

start : (a | b | c) {assert str(current) == 'b', str(current)};
a : A ;
b : B ;
c : C ;

A : 'a' ;
B : 'b' ;
C : [a-z] ;
