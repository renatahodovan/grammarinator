/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This is a very simple file, the "Hello World!" of grammars. This test checks
 * whether the most simple mechanisms (parser rules, lexer rules, and anonymous
 * tokens) work. The test also checks whether automatic PEP8 beautification
 * works (with the `--pep8` CLI option).
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir} --pep8
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-PARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

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
