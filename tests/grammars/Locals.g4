/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether parser rule local variables are declared
 * and handled correctly (even in the presence of type information).
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 --stdout
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 2 -n 5 --stdout

grammar Locals;

start locals[cnt=0, unused_and_uninitialized:int]
    : (Char {$cnt += 1})+ {assert(len(str(current)) == $cnt)}
    ;

Char
    : [a-z]
    ;
