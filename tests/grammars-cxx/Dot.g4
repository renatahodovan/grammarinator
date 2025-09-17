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

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir} -Ddot=any_ascii_letter
// TEST-BUILD-CXX: --generator={grammar}Generator --model={grammar}Model --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}.txt

grammar Dot;

options {
dot=any_ascii_char;
}

@header {
#include <cassert>

class DotModel : public grammarinator::runtime::DefaultModel {
public:
  DotModel() = default;
  DotModel(const DotModel& other) = delete;
  DotModel& operator=(const DotModel& other) = delete;
  DotModel(DotModel&& other) = delete;
  DotModel& operator=(DotModel&& other) = delete;
  ~DotModel() override = default;

  std::string charset(const grammarinator::runtime::Rule* node, int idx, const std::vector<std::string>& chars) override {
    if (node->name == "C") {
      char utf8[1] = { 0 };
      // dot option in grammar allows any printable 7-bit ASCII character, 0 included
      // command-line override tries to limit dot to 7-bit ASCII letters, 0 excluded
      assert(std::find(chars.begin(), chars.end(), "0") == chars.end());
      return "c";
    }
    return DefaultModel::charset(node, idx, chars);
  }
};
}


start : A . C;
A : 'aa' ;
B : 'bb' ;
C : . ;
