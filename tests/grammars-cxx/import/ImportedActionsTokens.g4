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
inline std::string ANSWER = "42";
}

@members {
std::string _answer() {
    return ANSWER;
}
}

tokens { Answer, Space }
