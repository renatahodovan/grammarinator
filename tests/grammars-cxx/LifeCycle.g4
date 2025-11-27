/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
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

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --serializer=grammarinator::runtime::SimpleSpaceSerializer --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 3 -o {tmpdir}/{grammar}A%d.txt
// TEST-PARSE: -g {grammar}.g4 -j 1 -r start --hidden WS -o {tmpdir}/population/j/ --tree-format json {tmpdir}/LifeCycleA0.txt {tmpdir}/LifeCycleA1.txt {tmpdir}/LifeCycleA2.txt
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 3 --population {tmpdir}/population/j/ --tree-format json -o {tmpdir}/{grammar}JB%d.txt --keep-trees --no-generate --no-recombine
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 3 --population {tmpdir}/population/j/ --tree-format json -o {tmpdir}/{grammar}JC%d.txt --keep-trees --no-generate --no-mutate
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 6 --population {tmpdir}/population/j/ --tree-format json -o {tmpdir}/{grammar}JD%d.txt --no-generate
// TEST-PARSE: -g {grammar}.g4 -j 1 -r start --hidden WS -o {tmpdir}/population/f/ --tree-format flatbuffers {tmpdir}/LifeCycleA0.txt {tmpdir}/LifeCycleA1.txt {tmpdir}/LifeCycleA2.txt
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 3 --population {tmpdir}/population/f/ --tree-format flatbuffers -o {tmpdir}/{grammar}FB%d.txt --keep-trees --no-generate --no-recombine
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 3 --population {tmpdir}/population/f/ --tree-format flatbuffers -o {tmpdir}/{grammar}FC%d.txt --keep-trees --no-generate --no-mutate
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 6 --population {tmpdir}/population/f/ --tree-format flatbuffers -o {tmpdir}/{grammar}FD%d.txt --no-generate

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
