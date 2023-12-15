/*
 * Copyright (c) 2024 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the processing of @init and @after rule
 * actions work as expected.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -o {tmpdir}/{grammar}%d.txt

grammar InitAfter;

start : r=wrapped_rule {assert $r.testValue == 'endValue', $r.testValue} ;

wrapped_rule returns [testValue]
@init {
$testValue = 'startValue'
}
@after {
$testValue = 'endValue'
}
: {assert $testValue == 'startValue', $testValue} A ;
A : 'a' ;
