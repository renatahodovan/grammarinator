/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * The test checks the handling of the ``dot`` wildcard both in lexer and parser
 * rules. Furthermore, it checks whether command-line override of the lexer dot
 * option (`-Ddot=`) works correctly.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir} -Ddot=any_ascii_letter
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 --model {grammar}Generator.{grammar}Model -o {tmpdir}/{grammar}.txt
// TEST-ANTLR: {grammar}.g4 -o {tmpdir}
// TEST-REPARSE: -p {grammar}Parser -l {grammar}Lexer -r start {tmpdir}/{grammar}%d.txt

grammar Dot;

options {
dot=any_ascii_char;
}

@header {

from grammarinator.runtime import DispatchingModel


class DotModel(DispatchingModel):

    def charset_C(self, node, idx, chars):
        # dot option in grammar allows any printable 7-bit ASCII character, 0 included
        # command-line override tries to limit dot to 7-bit ASCII letters, 0 excluded
        assert ord('0') not in chars, chars
        return 'c'
}


start : A . C;
A : 'aa' ;
B : 'bb' ;
C : . ;
