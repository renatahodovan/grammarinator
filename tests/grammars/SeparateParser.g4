/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether separate parser and lexer grammars are handled
 * properly.
 */

// TEST-PROCESS: {grammar}Parser.g4 {grammar}Lexer.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}Parser.g4 {grammar}Lexer.g4 -o {tmpdir}
// TEST-PARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

parser grammar SeparateParser;

start
  : TOKEN
  ;
