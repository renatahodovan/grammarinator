/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks the whole lifecycle of Grammarinator:
 *  - process an ANTLR4 grammar and create fuzzer/generator from it,
 *  - use the generated fuzzer to produce test cases that are
 *    serialized with the builtin space serializer,
 *  - build a tree population from the generated tests,
 *  - generate tests with the fuzzer again but utilize the
 *    previously created population, which enables the use of
 *    the evolutionary operators: mutate and recombine:
 *    - First, create tests with mutation only and keep the output trees.
 *    - Next, create tests with recombination only and keep the output trees.
 *    - Third, use both mutation and recombination on the population extended
 *      with the previously generated trees.
 * Population-related tasks (parsing, mutation, recombination) are checked using
 * both available tree file formats.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -r start -n 3 -s grammarinator.runtime.simple_space_serializer -o {tmpdir}/{grammar}A%d.txt
// TEST-PARSE: {grammar}.g4 -j 1 -i {tmpdir}/LifeCycleA0.txt {tmpdir}/LifeCycleA1.txt {tmpdir}/LifeCycleA2.txt -r start --hidden WS -o {tmpdir}/population/p/ --tree-format pickle
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -r start -n 3 --population {tmpdir}/population/p/ --tree-format pickle -o {tmpdir}/{grammar}PB%d.txt --keep-trees --no-generate --no-recombine
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -r start -n 3 --population {tmpdir}/population/p/ --tree-format pickle -o {tmpdir}/{grammar}PC%d.txt --keep-trees --no-generate --no-mutate
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 2 -r start -n 6 --population {tmpdir}/population/p/ --tree-format pickle -o {tmpdir}/{grammar}PD%d.txt --no-generate
// TEST-PARSE: {grammar}.g4 -j 1 -i {tmpdir}/LifeCycleA0.txt {tmpdir}/LifeCycleA1.txt {tmpdir}/LifeCycleA2.txt -r start --hidden WS -o {tmpdir}/population/j/ --tree-format json
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -r start -n 3 --population {tmpdir}/population/j/ --tree-format json -o {tmpdir}/{grammar}JB%d.txt --keep-trees --no-generate --no-recombine
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 1 -r start -n 3 --population {tmpdir}/population/j/ --tree-format json -o {tmpdir}/{grammar}JC%d.txt --keep-trees --no-generate --no-mutate
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -j 2 -r start -n 6 --population {tmpdir}/population/j/ --tree-format json -o {tmpdir}/{grammar}JD%d.txt --no-generate

grammar LifeCycle;

start : TEST testType ;

testType
     : PROCESS    # ProcessType
     | GENERATE   # GenerateType
     | MUTATE     # GenerateType
     | RECOMBINE  # GenerateType
     | PARSE      # ParseType
     ;

TEST : 'TEST' ;
PROCESS : 'PROCESS' ;
GENERATE : 'GENERATE' ;
MUTATE : 'MUTATE' ;
RECOMBINE : 'RECOMBINE' ;
PARSE : 'PARSE' ;

WS : [ \t\n\r] -> channel(HIDDEN);
