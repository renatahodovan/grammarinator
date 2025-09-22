// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_AFLTOOL_HPP
#define GRAMMARINATOR_TOOL_AFLTOOL_HPP

#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../util/print.hpp"
#include "../util/random.hpp"
#include "FlatBuffersTreeCodec.hpp"
#include "SubTreePopulation.hpp"
#include "Tool.hpp"
#include "TreeCodec.hpp"

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

namespace grammarinator {
namespace tool {

template<class GeneratorFactoryClass>
class AFLTool : public Tool<GeneratorFactoryClass> {
public:
  using SerializerFn = typename Tool<GeneratorFactoryClass>::SerializerFn;
  using TransformerFn = typename Tool<GeneratorFactoryClass>::TransformerFn;

private:
  const TreeCodec& codec;

public:
  explicit AFLTool(const GeneratorFactoryClass& generator_factory, const std::string& rule = "",
                   const runtime::RuleSize& limit = runtime::RuleSize::max(),
                   bool unrestricted = true, std::unordered_set<std::string> allowList = {}, std::unordered_set<std::string> blockList = {},
                   const std::vector<TransformerFn>& transformers = {}, SerializerFn serializer = nullptr, int memo_size = 0, const TreeCodec& codec = FlatBuffersTreeCodec())
      : Tool<GeneratorFactoryClass>(generator_factory, rule, limit, new SubTreePopulation(),
                                    true, true, true, unrestricted, allowList, blockList,
                                    transformers, serializer, memo_size),
        codec(codec) {
    this->allow_creator(this->mutators, "replace_from_pool", [this](auto i1, auto i2) { return replace_from_pool(i1); });
    this->allow_creator(this->mutators, "insert_quantified_from_pool", [this](auto i1, auto i2) { return insert_quantified_from_pool(i1); });
  }

  AFLTool(const AFLTool& other) = delete;
  AFLTool& operator=(const AFLTool& other) = delete;
  AFLTool(AFLTool&& other) = delete;
  AFLTool& operator=(AFLTool&& other) = delete;
  ~AFLTool() override = default;

  runtime::Rule* replace_from_pool(runtime::Individual* individual) {
    auto root = individual->root();
    auto annot = individual->annotations();

    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> lookup = annot->nodes_by_name();
    std::vector<std::tuple<runtime::Annotations::NodeKey, runtime::Rule*>> options;
    for (const auto& [key, nodes] : lookup) {
      for (auto node : nodes) {
        if (node->parent) {
          options.emplace_back(key, node);
        }
      }
    }

    const auto& node_info = annot->node_info();
    int root_tokens = node_info.at(root).tokens;
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto& [rule_name, node] : options) {
      int node_level = node_info.at(node).level;
      int node_tokens = node_info.at(node).tokens;
      auto indiv = static_cast<SubTreePopulation*>(this->population)->select_by_type(rule_name,
                                                                                     this->limit.depth - node_level,
                                                                                     this->limit.tokens - (root_tokens - node_tokens));
      if (indiv) {
          this->print_mutator("[{}] {} {}", __func__, rule_name, node->name);
          node->replace(indiv->root());
          delete node;
          delete indiv;
          return root;
      } else {
        GRAMMARINATOR_LOG_TRACE("{} not found in tree pool", rule_name.format());
        continue;
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* insert_quantified_from_pool(runtime::Individual* individual) {
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::tuple<runtime::Annotations::NodeKey, runtime::UnparserRuleQuantifier*>> options;
    for (const auto& [key, quant_nodes] : annot->quants_by_name()) {
      for (auto node : quant_nodes) {
        auto quant_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        if (quant_node->children.size() < quant_node->stop) {
          options.emplace_back(key, quant_node);
        }
      }
    }

    const auto& node_info = annot->node_info();
    int root_tokens = node_info.at(root).tokens;
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto& [rule_name, node] : options) {
      int node_level = node_info.at(node).level;
      auto indiv = static_cast<tool::SubTreePopulation*>(this->population)->select_by_type(rule_name,
                                                                                          this->limit.depth - node_level,
                                                                                          this->limit.tokens - root_tokens);
      if (indiv) {
          size_t pos = node->children.size() > 0 ? util::random_int<size_t>(0, node->children.size() - 1) : 0;
          node->insert_child(pos, indiv->root());
          delete indiv;
          this->print_mutator("[{}]", __func__);
          return root;
      } else {
        GRAMMARINATOR_LOG_TRACE("{} not found in tree pool", rule_name.format());
        continue;
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  void save_tree(runtime::Rule* root) {
    this->population->add_individual(root);
  }

  std::vector<uint8_t> encode(runtime::Rule* mutated_root) {
    return this->codec.encode(mutated_root);
  }

  size_t encode(runtime::Rule* mutated_root, uint8_t* data, size_t maxsize) {
    return this->codec.encode(mutated_root, data, maxsize);
  }

  runtime::Rule* decode(const uint8_t* data, size_t size) const {
    auto root = codec.decode(data, size);
    return root ? root : new runtime::UnparserRule(this->rule);
  }
};

}  // namespace tool
}  // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_AFLTOOL_HPP
