/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether recursive rules are handled properly. Moreover, it
 * also checks whether call stack depth control is properly handled both by
 * processor (depth info calculated automatically) and generator (parameterized
 * by the `-d` CLI option). (If depth control does not work, generator tends to
 * hit python interpreter recursion limits.)
 *
 * Note:
 *  - Because this test generates multiple outputs files, it exercises both
 *    single-process (`-j 1`) and multi-process (`-j N`) modes of generator.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 -d 5 -o {tmpdir}/{grammar}S%d.txt
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 2 -n 5 -d 5 -o {tmpdir}/{grammar}M%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-PARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}S%d.txt
// TEST-PARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}M%d.txt

grammar Recursive;

start
  : listofelements
  ;

listofelements
  : element
  | element ' ' listofelements
  | element ' | ' listofelements
  ;

element
  : 'pass'
  | '(' listofelements ')'
  ;
