/*
 * Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether semantic predicates can be used to bias choices at
 * alternatives.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar Semantic;

@header {
#include <cassert>
}

start
  : {0.5}? 'pass?'
  | {1.5}? 'pass!'
  | {0}? 'fail' {assert(false);}
  ;
