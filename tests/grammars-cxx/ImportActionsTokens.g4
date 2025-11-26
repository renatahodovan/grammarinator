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

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir} --lib import
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir} -lib import

grammar ImportActionsTokens;

import ImportedActionsTokens;

@header {
inline std::string QUESTION = "What do you get when you multiply six by nine?";
}

@members {
std::string _question() {
    return QUESTION;
}
}

tokens { Question, Space }

start:
    Question {static_cast<UnlexerRule*>(static_cast<UnparserRule*>(current)->last_child())->src = _question();}
    Space {static_cast<UnlexerRule*>(static_cast<UnparserRule*>(current)->last_child())->src = " ";}
    Answer {static_cast<UnlexerRule*>(static_cast<UnparserRule*>(current)->last_child())->src = _answer();}
    {assert(std::format("{}", *current) == "What do you get when you multiply six by nine? 42");};
