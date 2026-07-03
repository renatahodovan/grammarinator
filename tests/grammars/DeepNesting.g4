/*
 * Copyright (c) 2017-2026 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether deeply nested quantifiers/alternations (which would
 * exceed CPython's CO_MAXBLOCKS statically-nested block limit in a single rule
 * method) are auto-split into fragment helper methods so that the generated
 * Python fuzzer stays importable.
 *
 * `deepquant` carries a labelled element (`v=`) deep inside the nesting, forcing
 * a `local_ctx` that a fragment must receive as a parameter. `dotrule` uses the
 * `.` wildcard, which creates the internal, leading-underscore `_dot` rule.
 *
 * `deeptwice` is nested deep enough (~49 blocks) that a single cut is not
 * sufficient: the split must be applied repeatedly, producing more than one
 * fragment helper for the rule.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -n 5 -o {tmpdir}/{grammar}%d.txt
// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}

grammar DeepNesting;

start
  : deepquant deepalt dotrule deeptwice EOF
  ;

deepquant
  : ('a' ('b' ('c' ('d' ('e' ('f' ('g' ('h' ('i' (v='j' 'end'?)?)?)?)?)?)?)?)?)?)?
  ;

deepalt
  : ('t23' | ('t22' | ('t21' | ('t20' | ('t19' | ('t18' | ('t17' | ('t16' | ('t15' | ('t14' | ('t13' | ('t12' | ('t11' | ('t10' | ('t9' | ('t8' | ('t7' | ('t6' | ('t5' | ('t4' | ('t3' | ('t2' | ('t1' | 'z0')))))))))))))))))))))))
  ;

dotrule
  : .
  ;

deeptwice
  : ('a' ('b' ('c' ('d' ('e' ('f' ('g' ('h' ('i' ('j' ('k' ('l' ('m' ('n' ('o' 'p'?)?)?)?)?)?)?)?)?)?)?)?)?)?)?)?
  ;
