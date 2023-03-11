/*
 * Copyright (c) 2023 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether DefaultListener and DispatchingListener
 * work as expected.
 */

// TEST-PROCESS: {grammar}.g4 -o {tmpdir}
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 --listener grammarinator.runtime.DefaultListener -o {tmpdir}/{grammar}A%d.txt
// TEST-GENERATE: {grammar}Generator.{grammar}Generator -r start -j 1 -n 5 --listener {grammar}Generator.CustomListener -o {tmpdir}/{grammar}B%d.txt

grammar Listeners;

@header {

from grammarinator.runtime import DispatchingListener


class CustomListener(DispatchingListener):

    def __init__(self):
        self.enter_cnt = 0
        self.exit_cnt = 0

    def enter_a(self, node):
        self.enter_cnt += 1

    def exit_a(self, node):
        self.exit_cnt += 1

    def enter_b(self, node):
        self.enter_cnt += 1

    def exit_b(self, node):
        self.exit_cnt += 1

    def exit_start(self, node):
        assert self.enter_cnt == 1, self.enter_cnt
        assert self.exit_cnt == 1, self.exit_cnt
}


start : a | b;
a : A ;
b : B ;

A : 'a' ;
B : 'b' ;
