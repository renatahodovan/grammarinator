/*
 * Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
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
 * fall into infinite recursion.)
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -d 5 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

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
