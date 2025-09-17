/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether parser rule local variables are declared and handled
 * correctly.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 --stdout

grammar Locals;

@header {
#include <cassert>
}

start locals[int cnt=0, int unused_and_uninitialized]
    : (Char {$cnt++;})+ {assert(std::format("{}", *current).length() == $cnt);}
    ;

Char
    : [a-z]
    ;
