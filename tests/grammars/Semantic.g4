/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether semantic predicates can be used to bias choices at
 * alternatives.
 *
 * Note:
 *  - Because this test generates multiple outputs files, it exercises both
 *    single-process (`-j 1`) and multi-process (`-j N`) modes of generator.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 -o {tmpdir}/{grammar}S%d.txt
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 2 -n 5 -o {tmpdir}/{grammar}M%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar Semantic;

start
  : {0.5}? 'pass?'
  | {1.5}? 'pass!'
  | {0}? 'fail' {assert False, 'semantic predicate should have disabled this alternative'}
  ;
