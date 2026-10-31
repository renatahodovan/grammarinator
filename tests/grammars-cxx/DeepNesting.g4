/*
 * Copyright (c) 2026 Renata Hodovan, Akos Kiss, Piotr Oleś.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * When generating a Python fuzzer, deeply nested quantifiers/alternations
 * (which would exceed CPython's CO_MAXBLOCKS statically-nested block limit in a
 * single rule method) are outlined into helper methods so that the generated
 * Python fuzzer stays importable.
 *
 * C++ has no analogous limitation, but still, deep nesting must work in C++,
 * too. This test checks whether the Python outlining logic has no unintended
 * effects on the generated C++ fuzzer.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}%d.txt

grammar DeepNesting;

start
  : deepquant deepalt deeptwice EOF
  ;

deepquant
  : ('a' ('b' ('c' ('d' ('e' ('f' ('g' ('h' ('i' (v='j' 'end'+)+)+)+)+)+)+)+)+)+)+
  ;

deepalt
  : ('t23' | ('t22' | ('t21' | ('t20' | ('t19' | ('t18' | ('t17' | ('t16' | ('t15' | ('t14' | ('t13' | ('t12' | ('t11' | ('t10' | ('t9' | ('t8' | ('t7' | ('t6' | ('t5' | ('t4' | ('t3' | ('t2' | ('t1' | 'z0')))))))))))))))))))))))
  ;

deeptwice
  : ('a' ('b' ('c' ('d' ('e' ('f' ('g' ('h' ('i' ('j' ('k' ('l' ('m' ('n' ('o' 'p'+)+)+)+)+)+)+)+)+)+)+)+)+)+)+)+
  ;
