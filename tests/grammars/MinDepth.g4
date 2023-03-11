/*
 * Copyright (c) 2022-2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether dynamic depth adaptation works as expected.
 * 'c' should be generated, even if only 'b' is available within the
 * predefined depth. However, it's disabled by an inlined predicate,
 * hence the dynamic adaptation will enable the first branch.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -n 1 -o {tmpdir}/{grammar}%d.txt -d 2
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar MinDepth;

start : a | { False }? b ;

a : c ;

c : 'c' ;

b : 'b' ;
