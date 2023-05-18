/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * Tests handling of Unicode surrogate pairs.
 *
 * Note:
 *  - Surrogate pairs can be written but will be converted to complete
 *    Unicode characters when reading back, so ANTLR is not invoked to generate
 *    a parser.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -o {tmpdir}/{grammar}%d.txt --encoding utf-16 --encoding-errors surrogatepass

grammar SurrogatePairs;

start: SURROGATE NON_BMP ;

SURROGATE: '\ud83d\ude4f' ;

NON_BMP: '\u{01f64f}' ;
