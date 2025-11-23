/*
 * Copyright (c) 2024-2025 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether the trampoline functions of recurring labeled
 * alternatives create the correct tree structure.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --model={grammar}Model --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -n 5 -o {tmpdir}/{grammar}%d.txt

grammar RecurringLabelTrampolines;

@header {
#include <cassert>

class RecurringLabelTrampolinesModel : public grammarinator::runtime::DefaultModel {
private:
  int alt{1};
public:
  RecurringLabelTrampolinesModel() = default;
  RecurringLabelTrampolinesModel(const RecurringLabelTrampolinesModel& other) = delete;
  RecurringLabelTrampolinesModel& operator=(const RecurringLabelTrampolinesModel& other) = delete;
  RecurringLabelTrampolinesModel(RecurringLabelTrampolinesModel&& other) = delete;
  RecurringLabelTrampolinesModel& operator=(RecurringLabelTrampolinesModel&& other) = delete;
  ~RecurringLabelTrampolinesModel() override = default;

  int choice(const grammarinator::runtime::Rule* node, int idx, const std::vector<double>& weights) override {
    if (node->name == "start") {
      alt = 1 - alt;
      return alt;
    }
    return DefaultModel::choice(node, idx, weights);
  }
};
}

start
@after {
assert(current->name == "start");
assert(static_cast<ParentRule*>(current)->last_child()->type == Rule::UnparserRuleAlternativeType);
assert(static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->children.size() == 1);
assert(static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->last_child()->name == "start_Foo");
assert(static_cast<ParentRule*>(static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->last_child())->last_child()->name == "Bar");
assert(std::format("{}", *current) == "bar");

static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->last_child()->replace(start_Foo());

assert(current->name == "start");
assert(static_cast<ParentRule*>(current)->last_child()->type == Rule::UnparserRuleAlternativeType);
assert(static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->children.size() == 1);
assert(static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->last_child()->name == "start_Foo");
assert(static_cast<ParentRule*>(static_cast<ParentRule*>(static_cast<ParentRule*>(current)->last_child())->last_child())->last_child()->name == "Baz");
assert(std::format("{}", *current) == "baz");
}
    : Bar # Foo
    | Baz # Foo
    ;

Bar : 'bar' ;
Baz : 'baz' ;
