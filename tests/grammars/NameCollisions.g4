/*
 * Copyright (c) 2026 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks generated method names that collide with Python imports and builtins.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar NameCollisions;

start
  : {assert self._rule_sizes['never'].depth == float('inf')} Callable ClassVar Generator ParentRule Rule RuleSize inf+ CHARSET dict tuple str int float
  ;

inf : 'i';
dict : 'd';
tuple : 't';
str : 's';
int : 'n';
float : 'f';
never : 'b' never;

Callable : 'c';
ClassVar : 'v';
Generator : 'g';
ParentRule : 'p';
Rule : 'r';
RuleSize : 'z';
CHARSET : [a];
