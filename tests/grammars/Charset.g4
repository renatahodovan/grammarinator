/*
 * Copyright (c) 2020 Renata Hodovan, Akos Kiss.
 * Copyright (c) 2020 Sebastian Kimberk.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * Tests handling of charsets (especially with escaped characters).
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-PARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar Charset;

start
  : SPECIAL_ESCAPE NON_RANGE_DASH UNICODE_ESCAPE RANGE
  ;

SPECIAL_ESCAPE
  : [\-\]] [\]] [\-] [a\-] [\]a] [+\-]
  ;

NON_RANGE_DASH
  : [-a] [a-] [-] [--] [-\-] [-\--]
  ;

UNICODE_ESCAPE
  : [a\u1f01\u{1f01}b\u{0}\u{000000}]
  ;

RANGE
  : [a-zA-Z0-9] ["\\\u0000-\u001F] [a\u{100}-\u0f00] [---] [\--\-]
  ;
