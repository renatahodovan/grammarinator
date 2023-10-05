/*
 * Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
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
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar Charset;

start
  : SPECIAL_ESCAPE NON_RANGE_DASH UNICODE_ESCAPE RANGE UNICODE_NOTSET CHAR_RANGE USTR
  ;

SPECIAL_ESCAPE
  : [\-\]] [\]] [\-] [a\-] [\]a] [+\-]
  ;

NON_RANGE_DASH
  : [-a] [a-] [-] [--] [-\-] [-\--]
  ;

UNICODE_ESCAPE
  : [A\u1f01\u{1f01}B\u{0}\u{000000}]
  ;

RANGE
  : [a-zA-Z0-9] ["\\\u0000-\u001F] [a\u{100}-\u0f00] [---] [\--\-] [\u0043\u{0044}\u0045-\u{0046}\u{1F600}\t]
  ;

UNICODE_NOTSET
  : ~[\u0041-\u0050\ntu]
  ;

CHAR_RANGE
  : '\u{0047}'..'\u{0050}'
  ;

USTR
  : '\u{1F600}\u0041\n\u0042'
  ;
