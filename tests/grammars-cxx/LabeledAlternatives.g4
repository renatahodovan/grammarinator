/*
 * Copyright (c) 2018-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the labeled alternatives are handled correctly
 * (including the handling of variables within labeled alternatives and
 * labels starting with the name of the containing rule).
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar LabeledAlternatives;

start
    : x=Hello World           # HelloAlternative
    | Grammarinator y=Rulez   # GrammarinatorAlternative
    | Hello Grammarinator     # StartLastOption
    ;

Hello : 'hello' ;

World : 'world' ;

Grammarinator : 'grammarinator' ;

Rulez : 'rulez' ;
