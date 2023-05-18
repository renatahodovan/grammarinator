/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether command-line override of the dot option (`-Ddot=`)
 * works correctly.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir} -Ddot=any_ascii_letter
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 --model {grammar}Generator.DotModel -o {tmpdir}/{grammar}.txt

grammar DotOption;

options {
dot=any_ascii_char;
}

@header {

from grammarinator.runtime import DispatchingModel


class DotModel(DispatchingModel):

    def charset_start(self, node, idx, chars):
        # dot option in grammar allows any printable 7-bit ASCII character, 0 included
        # command-line override tries to limit dot to 7-bit ASCII letters, 0 excluded
        assert ord('0') not in chars, chars
        return 'a'
}


start : . ;
