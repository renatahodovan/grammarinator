/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the simple space transformer properly inserts spaces
 * in the output of generator. (If the transformer misbehaves, the ID rule will
 * consume all characters in the ANTLR-generated lexer and the parser will not
 * be able to match the input to the start rule.)
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -s grammarinator.runtime.simple_space_serializer -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-PARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar Whitespace;

start: 'keywords' 'must' 'be' 'separated' 'by' 'whitespace';

ID: [a-z]+;

WHITESPACE: [ \t\r\n] -> skip;
