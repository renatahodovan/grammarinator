/*
 * Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * Tests handling of implicit literals in parser rules.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --listener={grammar}Listener --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt

grammar ImplicitLiteral;

@header {
#include <cassert>

class ImplicitLiteralListener : public grammarinator::runtime::Listener {
private:
  bool hello_called{false};

public:
  ImplicitLiteralListener() = default;
  ImplicitLiteralListener(const ImplicitLiteralListener& other) = delete;
  ImplicitLiteralListener& operator=(const ImplicitLiteralListener& other) = delete;
  ImplicitLiteralListener(ImplicitLiteralListener&& other) = delete;
  ImplicitLiteralListener& operator=(ImplicitLiteralListener&& other) = delete;
  ~ImplicitLiteralListener() override = default;

  void exit_rule(grammarinator::runtime::Rule* node) override {
    if (node->name == "HELLO") {
      hello_called = true;
    } else if (node->name == "start") {
      assert(hello_called);
    }
  }
};
}


start : 'hello';
HELLO : 'hello';
