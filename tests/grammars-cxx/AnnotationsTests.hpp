// Copyright (c) 2026 Renata Hodovan.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef ANNOTATIONS_TESTS_HPP
#define ANNOTATIONS_TESTS_HPP

#include <grammarinator/runtime/Population.hpp>

#include <cassert>
#include <memory>

// Check clone annotations, empty indices, and invalidation after source edits.
static void test_annotations() {
  using namespace grammarinator::runtime;
  auto root = std::make_unique<UnparserRule>("start");
  auto quant = new UnparserRuleQuantifier(2, 0, 4);
  auto quantified = new UnparserRuleQuantified();
  quantified->add_child(new UnlexerRule("TOKEN", "abc", {3, 2}, false));
  quant->add_child(quantified);
  root->add_child(quant);
  Annotations source(root.get());
  {
    std::unique_ptr<Rule> copy(root->clone());
    Annotations annot(copy.get(), source);
    const auto& info = annot.node_info().at(copy.get());
    assert(info.level == 0 && info.depth == 4 && info.tokens == 2);
    assert(annot.nodes_by_name().size() == 3);
    assert(annot.rules_by_name().size() == 1);
    assert(annot.quants_by_name().size() == 1);
    auto copied_quant = static_cast<ParentRule*>(copy.get())->children[0];
    assert(annot.quants_by_name().begin()->second[0] == copied_quant);
    assert(annot.node_info().at(copied_quant).level == 1);
  }
  quant->remove();
  delete quant;
  root->add_child(new UnlexerRule("OTHER", "z", {1, 1}, false));
  source.reset();
  {
    std::unique_ptr<Rule> copy(root->clone());
    Annotations annot(copy.get(), source);
    assert(annot.rules_by_name().begin()->first.name == "OTHER");
    assert(annot.quants_by_name().empty());
    assert(annot.quants_by_name().empty());
    const auto& info = annot.node_info().at(copy.get());
    assert(info.level == 0 && info.depth == 2 && info.tokens == 1);
  }
  auto empty = std::make_unique<UnparserRule>("empty");
  Annotations empty_source(empty.get());
  std::unique_ptr<Rule> copy(empty->clone());
  Annotations annot(copy.get(), empty_source);
  assert(annot.nodes_by_name().empty() && annot.rules_by_name().empty());
  assert(annot.quants_by_name().empty() && annot.node_info().at(copy.get()).tokens == 0);
}

#endif  // ANNOTATIONS_TESTS_HPP
