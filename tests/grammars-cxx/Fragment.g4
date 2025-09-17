/*
 * Copyright (c) 2024-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether listeners see the correct names when lexer rules
 * refer to other lexer rules (usually, fragment rules).
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --listener={grammar}Listener --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 1 -o {tmpdir}/{grammar}%d.txt

grammar Fragment;

@header {
#include <cassert>
#include <map>
#include <string>

class FragmentListener : public grammarinator::runtime::Listener {
private:
  std::map<std::string, int> cnt_enters;
  std::map<std::string, int> cnt_exits;

public:
  FragmentListener() = default;
  FragmentListener(const FragmentListener& other) = delete;
  FragmentListener& operator=(const FragmentListener& other) = delete;
  FragmentListener(FragmentListener&& other) = delete;
  FragmentListener& operator=(FragmentListener&& other) = delete;
  ~FragmentListener() override = default;

  void enter_rule(grammarinator::runtime::Rule* node) override {
    cnt_enters[node->name] = cnt_enters.contains(node->name) ? cnt_enters[node->name] + 1 : 1;
  }

  void exit_rule(grammarinator::runtime::Rule* node) override {
    cnt_exits[node->name] = cnt_exits.contains(node->name) ? cnt_exits[node->name] + 1 : 1;
    if (node->name == "start") {
      assert(cnt_enters == (std::map<std::string, int>{{"start", 1}, {"A", 1}, {"B", 1}, {"C", 1}, {"D", 1}, {"E", 1}}));
      assert(cnt_exits == (std::map<std::string, int>{{"start", 1}, {"A", 1}, {"B", 1}, {"C", 1}, {"D", 1}, {"E", 1}}));
    }
  }
};
}


start : A;
A : 'a' B ;
B : 'b' C ;
fragment C : 'c' D ;
fragment D : 'd' E ;
E : 'e' ;
