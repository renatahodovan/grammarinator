/*
 * Copyright (c) 2024-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the trampoline functions of recurring labeled
 * alternatives create the correct tree structure.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -m {grammar}Generator.{grammar}Model -j 1 -n 5 -o {tmpdir}/{grammar}%d.txt

grammar RecurringLabelTrampolines;

@header {
from grammarinator.runtime import DispatchingModel

class RecurringLabelTrampolinesModel(DispatchingModel):

    def __init__(self):
        self.alt = 1

    def choice_start(self, node, idx, weights):
        self.alt = 1 - self.alt
        return self.alt

}

start
@after {
assert current.name == 'start', current.name
assert isinstance(current.last_child, UnparserRuleAlternative), repr(current.last_child)
assert len(current.last_child.children) == 1, current.last_child.children
assert current.last_child.last_child.name == 'start_Foo', repr(current.last_child.last_child)
assert current.last_child.last_child.last_child.name == 'Bar', repr(current.last_child.last_child.last_child)
assert str(current) == 'bar', str(current)

current.last_child.last_child.replace(self.start_Foo())

assert current.name == 'start', current.name
assert isinstance(current.last_child, UnparserRuleAlternative), repr(current.last_child)
assert len(current.last_child.children) == 1, current.last_child.children
assert current.last_child.last_child.name == 'start_Foo', repr(current.last_child.last_child)
assert current.last_child.last_child.last_child.name == 'Baz', repr(current.last_child.last_child.last_child)
assert str(current) == 'baz', str(current)
}
    : Bar # Foo
    | Baz # Foo
    ;

Bar : 'bar' ;
Baz : 'baz' ;
