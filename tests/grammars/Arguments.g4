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
 * properly down in the tree.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -n 5 --stdout

grammar Arguments;

start
    : res=expr['int'] {assert str($res) == "len(list('string'))"}
    ;

expr args[typ]
    : {$typ == 'int'}? 'len(' expr['list'] ')'
    | {$typ == 'list'}? 'list(' expr['string'] ')'
    | {$typ == 'string'}? '\'string\''
    ;
