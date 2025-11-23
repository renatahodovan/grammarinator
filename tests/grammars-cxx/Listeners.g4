/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether Listeners work as expected.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build/L
// TEST-GENERATE-CXX: {tmpdir}/build/L/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}L%d.txt
// TEST-BUILD-CXX: --generator={grammar}Generator --listener={grammar}Listener --includedir={tmpdir} --builddir={tmpdir}/build/C
// TEST-GENERATE-CXX: {tmpdir}/build/C/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}C%d.txt

grammar Listeners;

@header {
#include <cassert>

class ListenersListener : public grammarinator::runtime::Listener {
private:
  int enter_cnt{0};
  int exit_cnt{0};

public:
  ListenersListener() = default;
  ListenersListener(const ListenersListener& other) = delete;
  ListenersListener& operator=(const ListenersListener& other) = delete;
  ListenersListener(ListenersListener&& other) = delete;
  ListenersListener& operator=(ListenersListener&& other) = delete;
  ~ListenersListener() override = default;

  void enter_rule(grammarinator::runtime::Rule* node) override {
    if (node->name == "a" || node->name == "b") {
      enter_cnt++;
    }
  }

  void exit_rule(grammarinator::runtime::Rule* node) override {
    if (node->name == "a" || node->name == "b") {
      exit_cnt++;
    } else if (node->name == "start") {
      assert(enter_cnt == 1);
      assert(exit_cnt == 1);
    }
  }
};
}


start : a | b;
a : A ;
b : B ;

A : 'a' ;
B : 'b' ;
