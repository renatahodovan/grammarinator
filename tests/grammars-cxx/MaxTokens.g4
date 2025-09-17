/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the maximum token restriction is respected by both
 * alternations and quantifiers.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --model={grammar}Model --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt --max-tokens 7

grammar MaxTokens;

@header {
#include <cassert>

class MaxTokensModel : public grammarinator::runtime::DefaultModel {
public:
  MaxTokensModel() = default;
  MaxTokensModel(const MaxTokensModel& other) = delete;
  MaxTokensModel& operator=(const MaxTokensModel& other) = delete;
  MaxTokensModel(MaxTokensModel&& other) = delete;
  MaxTokensModel& operator=(MaxTokensModel&& other) = delete;
  ~MaxTokensModel() override = default;

  bool quantify(const grammarinator::runtime::Rule* node, int idx, int cnt, int start, int stop) override {
    if (node->name == "start") {
      return true;
    }
    return DefaultModel::quantify(node, idx, cnt, start, stop);
  }
};
}


start : a b+ c {auto str_current = std::format("{}", *current); assert(str_current == "aaabbbc" || str_current == "aaaabbc");};
a : A A A | A A A A;
b : B ;
c : C ;
A : 'a' ;
B : 'b' ;
C : 'c' ;
