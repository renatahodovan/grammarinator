/*
 * Copyright (c) 2022-2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether simple alternations, i.e., alternations containing
 * alternatives with a single literal or rule reference, are handled/optimized
 * correctly.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar SimpleAlternations;

start: simple_literals | simple_rules | simple_mixed_alts | SIMPLE_MIXED_LEXER_ALTS ;

simple_literals : 'a' | 'b' | 'c' | '\r\n';

simple_rules : d | E | F ;

d : D ;

simple_mixed_alts : g | H | 'i' | '\r\n';

SIMPLE_MIXED_LEXER_ALTS : 'j' | 'k' | D ;

g : G ;

D : 'd' ;

E : 'e' ;

F : 'f' ;

G : 'g' ;

H : 'h' ;
