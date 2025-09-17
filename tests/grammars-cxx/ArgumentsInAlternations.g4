/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether parser rule arguments are propagated properly down
 * the tree, even in an alternation that seems to contain "simple" alternatives
 * only.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}%d.txt

grammar ArgumentsInAlternations;

@header {
#include <cassert>
}

start : a[1] | b[1, 1];
a[int x=0] : 'a' {assert($x == 1);};
b[int x=0, int y=0] : 'b' {assert($x == 1 && $y == 1);};
