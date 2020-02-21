/*
 * Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the processor properly supports the `--no-action`
 * CLI option.
 *
 * Note:
 *  - Because ANTLR does not support the suppression of actions and the
 *    action in the grammar triggers an assertion failure, the parser generated
 *    by ANTLR cannot be used to parse the output of generator (so it's not
 *    invoked).
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir} --no-action
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -o {tmpdir}/{grammar}%d.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}

grammar NoAction;

start
  : 'pass' {assert False, 'actions must be disabled'}
  ;
