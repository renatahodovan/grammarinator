/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether parser rule arguments are propagated
 * properly down in the tree. Plus it checks the parsing of more
 * complex argument lists.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 --stdout

grammar Arguments;

@header {
#include <cassert>
#include <list>
#include <string>
}

start
    : res=expr["int", {1, 2, 3}] {assert($res->format() == "len(list('string'))");}
    ;

expr[std::string typ="no=ne", std::list<int> unused={}]
    : {$typ == "int"}? 'len(' expr["list", std::list<int>{20, 40}] ')'
    | {$typ == "list"}? 'list(' expr["string", std::list<int>{3 < 2, (1 + 1) * 4, 10 / 2}] ')'
    | {$typ == "string"}? '\'string\''
    ;
