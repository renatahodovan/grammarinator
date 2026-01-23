/*
 * Copyright (c) 2024-2026 Renata Hodovan, Akos Kiss.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

/*
 * This test checks whether alternatives and quantifiers within recurring
 * labeled alternatives are numbered uniquely.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --model={grammar}Model --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r start -o {tmpdir}/{grammar}%d.txt

grammar RecurringLabeledAlternatives;

@header {
#include <cassert>

class RecurringLabeledAlternativesModel : public grammarinator::runtime::DefaultModel {
public:
  RecurringLabeledAlternativesModel() = default;
  RecurringLabeledAlternativesModel(const RecurringLabeledAlternativesModel& other) = delete;
  RecurringLabeledAlternativesModel& operator=(const RecurringLabeledAlternativesModel& other) = delete;
  RecurringLabeledAlternativesModel(RecurringLabeledAlternativesModel&& other) = delete;
  RecurringLabeledAlternativesModel& operator=(RecurringLabeledAlternativesModel&& other) = delete;
  ~RecurringLabeledAlternativesModel() override = default;

  int choice(const grammarinator::runtime::Rule* node, int idx, const std::vector<double>& weights) override {
    assert(node->name == "start" || node->name == "start_Binary");
    if (node->name == "start_Binary") {
      assert(idx == 1);
    }
    return DefaultModel::choice(node, idx, weights);
  }

  bool quantify(const grammarinator::runtime::Rule* node, int idx, int cnt, int start, int stop, double prob = 0.5) override {
    assert(node->name == "start_Binary");
    assert(idx == 1);
    return DefaultModel::quantify(node, idx, cnt, start, stop, prob);
  }
};
}

start
    : {0}? ID (('+' | '-') ID)+   # Binary
    | {0}? ('++' | '--') ID       # Unary
    | ID (('*'|'/') ID)+          # Binary
    | {0}? ID ('++' | '--')       # Unary
    ;

ID : [a-z] ;
