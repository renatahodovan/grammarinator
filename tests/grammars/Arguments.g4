/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
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

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 --stdout
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 2 -n 5 --stdout

grammar Arguments;

start
    : res=expr['int', [1, 2, 3]] {assert str($res) == "len(list('string'))"}
    ;

expr[typ='no=ne', unused='none']
    : {$typ == 'int'}? 'len(' expr['list', [(v * 2) for k, v in {'a<=c': 10, 'b\'c': 20}.items()]] ')'
    | {$typ == 'list'}? 'list(' expr['string', [3 < 2, (1 + 1) * 4, 10 / 2]] ')'
    | {$typ == 'string'}? '\'string\''
    ;
