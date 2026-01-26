/*
 * Copyright (c) 2024-2026 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether alternatives and quantifiers within recurring
 * labeled alternatives are numbered uniquely.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -m {grammar}Generator.{grammar}Model -j 1 -o {tmpdir}/{grammar}%d.txt

grammar RecurringLabeledAlternatives;

@header {
from grammarinator.runtime import DefaultModel

class RecurringLabeledAlternativesModel(DefaultModel):

    def choice(self, node, idx, weights):
        assert node.name in ['start', 'start_Binary'], node.name
        if node.name == 'start_Binary':
            assert idx == 1, idx
        return super().choice(node, idx, weights)

    def quantify(self, node, idx, cnt, start, stop, prob=0.5):
        assert node.name == 'start_Binary', node.name
        assert idx == 1, idx
        return super().quantify(node, idx, cnt, start, stop, prob)
}

start
    : {0}? ID (('+' | '-') ID)+   # Binary
    | {0}? ('++' | '--') ID       # Unary
    | ID (('*'|'/') ID)+          # Binary
    | {0}? ID ('++' | '--')       # Unary
    ;

ID : [a-z] ;
