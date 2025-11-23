/*
 * Copyright (c) 2020-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether command-line override of options (`-D`) works
 * correctly by specifying the superclass using the CLI.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir} -DsuperClass=SuperGenerator
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar SuperClassOption;

options {
superClass=None;
}

start
  : {InheritedRule(current);}
  ;
