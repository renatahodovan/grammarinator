/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether custom initial weights work as expected.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 --weights custom_weights.json -o {tmpdir}/{grammar}%d.txt

grammar CustomWeights;

@header {
#include <cassert>
}

start : (a | b | c) {assert(std::format("{}", *current) == "b");};
a : A ;
b : B ;
c : C ;

A : 'a' ;
B : 'b' ;
C : [a-z] ;
