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

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -o {tmpdir}/{grammar}%d.txt

grammar ChildAccessors;

@header {
#include <cassert>
}

start: a=altTest q=quantTest {assert(static_cast<UnparserRule*>($a)->get_child("A") && static_cast<UnparserRule*>($q)->get_child("B"));};

altTest: A | {false}? B;
quantTest: B+;

A: 'a';
B: 'b';
