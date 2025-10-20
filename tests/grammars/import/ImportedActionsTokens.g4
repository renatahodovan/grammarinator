/*
 * Copyright (c) 2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/* This grammar is used by ../ImportActionsTokens.g4 */

grammar ImportedActionsTokens;

@header {
ANSWER = '42'
}

@members {
def _answer(self):
    return ANSWER
}

tokens { Answer, Space }
