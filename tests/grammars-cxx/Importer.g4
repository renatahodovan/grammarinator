/*
 * Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the grammar import mechanism (using rules of a
 * different grammar) works, i.e.,
 * - a grammar can import multiple other grammars,
 * - even an imported grammar can import further grammar(s),
 * - if more than one imported grammar defines a rule, the first version found
 *   is used,
 * - both lexical and parser imported rules can be overridden.
 *
 * This test also checks that imports work even from a different directory (via
 * the `--lib` CLI option).
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir} --lib import
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir} -lib import
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar Importer;

import Importee1, Importee2;
// inherits Importee1.Token1 which hides Importee2.Token1
// inherits Importee3.Token2 which hides Importee2.Token2
// inherits Importee1.Token3 which hides Importee2.Token3
// inherits Importee2.Token4

start: Token1 Token2 Token3 Token4 Token5;  // overrides Importee1.start

Token5: '\n';  // adds Token5
