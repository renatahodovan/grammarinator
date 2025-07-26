/*
 * Copyright (c) 2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the children accessors work across alternatives
 * and quantifiers.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -o {tmpdir}/{grammar}%d.txt

grammar ChildAccessors;

start: a=altTest q=quantTest {assert getattr($a, 'A') and getattr($q, 'B')};

altTest: A | {False}? B;
quantTest: B+;

A: 'a';
B: 'b';
