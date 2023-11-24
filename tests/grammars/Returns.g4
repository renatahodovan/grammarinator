/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether parser rule returns are propagated properly up in
 * the tree. Plus it checks the parsing of type notation in returns.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 -d=5 --stdout
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 2 -n 5 -d=5 --stdout

grammar Returns;

tokens { VAR }

@header {
def exec_op(op1, op, op2):
    return {'+': lambda: op1 + op2,
            '-': lambda: op1 - op2,
            '*': lambda: op1 * op2}[op]()
}

start
    : res=expr '==' v=VAR {$v.src = str($res.result); assert(eval(str($res))) == float(str($res.result));}
    ;

expr returns [result=0, int unused_and_uninitialized]
    : '(' op1=expr op='*' op2=expr ')' {$result = exec_op($op1.result, str($op), $op2.result)}
    | '(' op1=expr op=('+' | '-') op2=expr ')' {$result = exec_op($op1.result, str($op), $op2.result)}
    | num=Number {$result = float(str($num))}
    ;

Number
    : [1-9][0-9]* ('.' [0-9]+)?
    ;
