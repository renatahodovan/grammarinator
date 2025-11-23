/*
 * Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This is a very simple file, the "Hello World!" of grammars. This test checks
 * whether the most simple mechanisms (parser rules, lexer rules, and anonymous
 * tokens) work.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar Hello;

start: hello ' ' grammarinator '!';

hello: H E L L O;

grammarinator: G R A M M A R I N A T O R;

A: 'a';
E: 'e';
G: 'G';
H: 'H';
I: 'i';
L: 'l';
M: 'm';
N: 'n';
O: 'o';
R: 'r';
T: 't';
