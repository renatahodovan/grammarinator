/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether curly braces are handled properly even
 * if they are placed in predicates, actions, or tokens.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar Curly;

start
  : name '{'
  | {'{name}' == '0'}? 'fail' {assert False, 'should not choose this alternative'}
  ;

name
  : 'pass' {assert '{name}' != '0'}
  ;
