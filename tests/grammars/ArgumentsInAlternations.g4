/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
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

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 -o {tmpdir}/{grammar}%d.txt

grammar ArgumentsInAlternations;

start : a[1] | b[1, 1];
a[x=0] : 'a' {assert $x == 1};
b[x=0, y=0] : 'b' {assert $x == 1 and $y == 1};
