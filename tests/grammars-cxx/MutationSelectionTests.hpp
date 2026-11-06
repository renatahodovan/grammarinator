// Copyright (c) 2026 Renata Hodovan.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef MUTATION_SELECTION_TESTS_HPP
#define MUTATION_SELECTION_TESTS_HPP

#include <grammarinator/runtime.hpp>
#include <grammarinator/tool/AFLTool.hpp>
#include <grammarinator/tool/DefaultGeneratorFactory.hpp>

#include <cassert>
#include <memory>

// Exercise successful and exhausted searches, donors, limits, and parent links.
template<class Generator>
static void test_mutation_selection() {
  using namespace grammarinator;
  using namespace runtime;
  using Factory = tool::DefaultGeneratorFactory<Generator>;
  auto root = std::make_unique<UnparserRule>("start");
  auto quant = new UnparserRuleQuantifier(0, 0, 8);
  root->add_child(quant);
  for (int i = 0; i < 4; ++i) {
    auto child = new UnparserRuleQuantified();
    auto item = new UnparserRule("item");
    item->add_child(new UnlexerRule("TOKEN", i % 2 ? "a" : "b", {1, 1}, false));
    child->add_child(item);
    quant->add_child(child);
  }
  tool::FlatBuffersTreeCodec codec;
  auto original = codec.encode(root.get());
  for (const std::string name : {"delete_quantified", "replicate_quantified", "shuffle_quantifieds", "hoist_rule",
                                 "swap_local_nodes", "insert_local_node", "unrestricted_delete", "unrestricted_hoist_rule",
                                 "replace_from_pool", "insert_quantified_from_pool", "replace_node", "insert_quantified"}) {
    tool::AFLTool<Factory> tool(Factory(), "start", {12, 40}, true, {name}, {}, {}, NoSpaceSerializer, 0, codec);
    tool.save_tree(root.get());
    for (unsigned seed = 0; seed < 100; ++seed) {
      util::random_engine.seed(seed);
      Individual recipient(root->clone()), donor(root->clone());
      Rule* result = name == "replace_node" || name == "insert_quantified"
                      ? tool.recombine(&recipient, &donor) : tool.mutate(&recipient);
      assert(codec.encode(donor.root()) == original);
      if (!result) {
        assert(codec.encode(recipient.root()) == original);
        continue;
      }
      Annotations annot(result);
      const auto& info = annot.node_info().at(result);
      assert(info.depth <= 12 && info.tokens <= 40);
      std::vector<Rule*> pending{result};
      while (!pending.empty()) {
        auto node = pending.back();
        pending.pop_back();
        if (node->type != Rule::UnlexerRuleType) {
          for (auto child : static_cast<ParentRule*>(node)->children) {
            assert(child->parent == node);
            pending.push_back(child);
          }
        }
      }
      auto bytes = codec.encode(result);
      std::unique_ptr<Rule> decoded(codec.decode(bytes.data(), bytes.size()));
      assert(decoded && NoSpaceSerializer(decoded.get()) == NoSpaceSerializer(result));
    }
  }
}

#endif  // MUTATION_SELECTION_TESTS_HPP
