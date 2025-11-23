/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * Tests handling of unicode property escapes.
 */

// TEST-PROCESS-CXX: {grammar}Parser.g4 {grammar}Lexer.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}Parser.g4 {grammar}Lexer.g4 -o {tmpdir}
// TEST-SKIP: difference between Unicode versions used by Grammarinator and ANTLR
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

parser grammar UnicodePropertiesParser;

options {
  tokenVocab = UnicodePropertiesLexer;
}

start : UPROP GENERAL ENUM_BLOCK ENUM_SCRIPT INVERTED EXTRAS INVERTED_EXTRAS;
