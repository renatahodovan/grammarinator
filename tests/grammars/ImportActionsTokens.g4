/*
 * Copyright (c) 2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the grammar import mechanism works for named
 * actions and tokens specifications.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir} --lib import
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir} -lib import

grammar ImportActionsTokens;

import ImportedActionsTokens;

@header {
QUESTION = 'What do you get when you multiply six by nine?'
}

@members {
def _question(self):
    return QUESTION
}

tokens { Question, Space }

start:
    Question {current.last_child.src = self._question()}
    Space {current.last_child.src = ' '}
    Answer {current.last_child.src = self._answer()}
    {assert str(current) == 'What do you get when you multiply six by nine? 42'};
