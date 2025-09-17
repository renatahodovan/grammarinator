/*
 * Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether curly braces are handled properly even
 * if they are placed in predicates, actions, or tokens.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar Curly;

@header {
#include <cassert>
#include <string>
}

start
  : name '{'
  | {std::string("{name}") == std::string("0")}? 'fail' {assert(false && "should not choose this alternative");}
  ;

name
  : 'pass' {assert(std::string("{name}") != std::string("0"));}
  ;
