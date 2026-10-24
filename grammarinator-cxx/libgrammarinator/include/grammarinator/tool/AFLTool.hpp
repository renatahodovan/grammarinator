// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_AFLTOOL_HPP
#define GRAMMARINATOR_TOOL_AFLTOOL_HPP

#include "../runtime/Model.hpp"
#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../runtime/WeightedModel.hpp"
#include "../util/print.hpp"
#include "../util/random.hpp"
#include "FlatBuffersTreeCodec.hpp"
#include "SubTreePopulation.hpp"
#include "Tool.hpp"
#include "TreeCodec.hpp"

#include <xxhash.h>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <memory>
#include <string>
#include <tuple>
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

  // Hashes of the pool subtrees used by the current mutation, and by the
  // last emitted mutation.
  std::vector<XXH64_hash_t> pool_picks;
  std::vector<XXH64_hash_t> emitted_pool_picks;

  static constexpr char pool_file_magic[8] = {'G', 'R', 'S', 'T', 'P', 'O', 'O', 'L'};

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
    this->allow_creator(this->mutators, "replace_quantifier_from_pool", [this](auto i1, auto i2) { return replace_quantifier_from_pool(i1); });
    this->allow_creator(this->mutators, "wrap_from_pool", [this](auto i1, auto i2) { return wrap_from_pool(i1); });
    this->allow_creator(this->mutators, "regenerate_rare", [this](auto i1, auto i2) { return regenerate_rare(i1); });
  }

  AFLTool(const AFLTool& other) = delete;
  AFLTool& operator=(const AFLTool& other) = delete;
  AFLTool(AFLTool&& other) = delete;
  AFLTool& operator=(AFLTool&& other) = delete;
  ~AFLTool() override { delete this->population; }

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
      XXH64_hash_t hash;
      auto indiv = static_cast<SubTreePopulation*>(this->population)->select_by_type(rule_name,
                                                                                     this->limit.depth - node_level,
                                                                                     this->limit.tokens - (root_tokens - node_tokens),
                                                                                     false, &hash);
      if (indiv) {
          pool_picks.push_back(hash);
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
      // Insert a quantified node (i.e., a child of a compatible quantifier) from the pool.
      runtime::Annotations::NodeKey quantified_key(rule_name.name, runtime::Annotations::NodeKey::QuantifiedKey, rule_name.idx);
      XXH64_hash_t hash;
      auto indiv = static_cast<tool::SubTreePopulation*>(this->population)->select_by_type(quantified_key,
                                                                                          this->limit.depth - node_level,
                                                                                          this->limit.tokens - root_tokens,
                                                                                          false, &hash);
      if (indiv) {
          pool_picks.push_back(hash);
          size_t pos = node->children.size() > 0 ? util::random_int<size_t>(0, node->children.size() - 1) : 0;
          node->insert_child(pos, indiv->root());
          delete indiv;
          this->print_mutator("[{}]", __func__);
          return root;
      } else {
        GRAMMARINATOR_LOG_TRACE("{} not found in tree pool", quantified_key.format());
        continue;
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Replace a whole quantifier node with a compatible one from the pool.
  runtime::Rule* replace_quantifier_from_pool(runtime::Individual* individual) {
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::tuple<runtime::Annotations::NodeKey, runtime::Rule*>> options;
    for (const auto& [key, quant_nodes] : annot->quants_by_name()) {
      for (auto node : quant_nodes) {
        options.emplace_back(key, node);
      }
    }

    const auto& node_info = annot->node_info();
    int root_tokens = node_info.at(root).tokens;
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto& [rule_name, node] : options) {
      int node_level = node_info.at(node).level;
      int node_tokens = node_info.at(node).tokens;
      XXH64_hash_t hash;
      auto indiv = static_cast<SubTreePopulation*>(this->population)->select_by_type(rule_name,
                                                                                     this->limit.depth - node_level,
                                                                                     this->limit.tokens - (root_tokens - node_tokens),
                                                                                     false, &hash);
      if (!indiv) {
        GRAMMARINATOR_LOG_TRACE("{} not found in tree pool", rule_name.format());
        continue;
      }
      if (indiv->root()->equalTokens(*node)) {
        delete indiv;
        continue;
      }
      pool_picks.push_back(hash);
      this->print_mutator("[{}] {}", __func__, rule_name);
      node->replace(indiv->root());
      delete node;
      delete indiv;
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Wrap a node into a pool subtree of the same rule that embeds the rule
  // again, in place of the embedded occurrence.
  runtime::Rule* wrap_from_pool(runtime::Individual* individual) {
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::tuple<runtime::Annotations::NodeKey, runtime::Rule*>> options;
    for (const auto& [key, nodes] : annot->rules_by_name()) {
      for (auto node : nodes) {
        if (node->type == runtime::Rule::UnparserRuleType) {
          options.emplace_back(key, node);
        }
      }
    }

    const auto& node_info = annot->node_info();
    int root_tokens = node_info.at(root).tokens;
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto& [rule_name, node] : options) {
      int node_level = node_info.at(node).level;
      int node_depth = node_info.at(node).depth;
      int node_tokens = node_info.at(node).tokens;
      // Select a subtree of the same rule from the pool that embeds the rule
      // again, put it in place of the node, and put the node in place of
      // one of the embedded occurrences.
      XXH64_hash_t hash;
      auto indiv = static_cast<SubTreePopulation*>(this->population)->select_by_type(rule_name,
                                                                                     this->limit.depth - node_level,
                                                                                     this->limit.tokens - (root_tokens - node_tokens),
                                                                                     true, &hash);
      if (!indiv) {
        GRAMMARINATOR_LOG_TRACE("{} not found in tree pool", rule_name.format());
        continue;
      }

      auto wrapper = indiv->root();
      auto wrapper_annot = indiv->annotations();
      const auto& wrapper_info = wrapper_annot->node_info();
      int wrapper_tokens = wrapper_info.at(wrapper).tokens;
      std::vector<runtime::Rule*> holes;
      auto holes_it = wrapper_annot->rules_by_name().find(rule_name);
      if (holes_it != wrapper_annot->rules_by_name().end()) {
        for (auto hole : holes_it->second) {
          if (node_level + wrapper_info.at(hole).level + node_depth <= this->limit.depth
              && root_tokens + wrapper_tokens - wrapper_info.at(hole).tokens <= this->limit.tokens) {
            holes.push_back(hole);
          }
        }
      }
      if (holes.empty()) {
        delete indiv;
        continue;
      }

      auto hole = holes[util::random_int<size_t>(0, holes.size() - 1)];
      pool_picks.push_back(hash);
      this->print_mutator("[{}] {}", __func__, rule_name);
      node->replace(wrapper);
      delete indiv;
      hole->replace(node);
      delete hole;
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Regenerate a random subtree like regenerate_rule, preferring the
  // alternatives that are rare in the pool.
  runtime::Rule* regenerate_rare(runtime::Individual* individual) {
    // Weight the alternatives inversely to how many distinct subtrees of the
    // pool chose them, so that rarely seen (or never seen) alternatives are
    // preferred during regeneration.
    runtime::WeightedModel::AltMap weights;
    runtime::WeightedModel::QuantMap probs;
    for (const auto& [key, count] : static_cast<SubTreePopulation*>(this->population)->alt_counts()) {
      weights[key] = 1.0 / (1.0 + count);
    }
    return this->regenerate_rule(individual, [&weights, &probs](runtime::Model* model) { return new runtime::WeightedModel(model, weights, probs); });
  }

  // Mutate a tree, keeping track of the pool subtrees used by the mutation.
  runtime::Rule* mutate(runtime::Individual* individual = nullptr) {
    pool_picks.clear();
    return Tool<GeneratorFactoryClass>::mutate(individual);
  }

  // Record that the result of the last mutation was emitted, i.e., the pool
  // subtrees it used got a chance to prove useful.
  void record_pool_uses() {
    static_cast<SubTreePopulation*>(this->population)->record_uses(pool_picks);
    emitted_pool_picks = pool_picks;
  }

  // Record that the last emitted mutation result was found interesting.
  void record_pool_successes() {
    static_cast<SubTreePopulation*>(this->population)->record_successes(emitted_pool_picks);
    emitted_pool_picks.clear();
  }

  // Save the n most successfully used subtrees of the pool with their usage
  // statistics.
  bool save_pool(const std::string& path, size_t n) {
    std::ofstream file(path, std::ios::binary | std::ios::trunc);
    if (!file) {
      GRAMMARINATOR_LOG_WARN("Cannot write subtree pool file {}", path);
      return false;
    }
    file.write(pool_file_magic, sizeof(pool_file_magic));
    for (const auto& [node, key, successes, uses] : static_cast<SubTreePopulation*>(this->population)->best_subtrees(n)) {
      std::vector<uint8_t> data = codec.encode(node);
      if (data.empty()) {
        continue;
      }
      uint32_t name_size = key.name.size();
      int32_t fields[] = {static_cast<int32_t>(key.type), key.idx, successes, uses};
      uint32_t data_size = data.size();
      file.write(reinterpret_cast<const char*>(&name_size), sizeof(name_size));
      file.write(key.name.data(), name_size);
      file.write(reinterpret_cast<const char*>(fields), sizeof(fields));
      file.write(reinterpret_cast<const char*>(&data_size), sizeof(data_size));
      file.write(reinterpret_cast<const char*>(data.data()), data_size);
    }
    return static_cast<bool>(file);
  }

  // Load subtrees saved by save_pool into the pool. Their usage statistics
  // are halved to let the new session revise them sooner.
  bool load_pool(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    char magic[sizeof(pool_file_magic)];
    if (!file.read(magic, sizeof(magic)) || !std::equal(magic, magic + sizeof(magic), pool_file_magic)) {
      GRAMMARINATOR_LOG_WARN("Cannot read subtree pool file {}", path);
      return false;
    }
    uint32_t name_size;
    while (file.read(reinterpret_cast<char*>(&name_size), sizeof(name_size))) {
      std::string name(name_size, '\0');
      int32_t fields[4];
      uint32_t data_size;
      if (!file.read(name.data(), name_size)
          || !file.read(reinterpret_cast<char*>(fields), sizeof(fields))
          || !file.read(reinterpret_cast<char*>(&data_size), sizeof(data_size))) {
        break;
      }
      std::vector<uint8_t> data(data_size);
      if (!file.read(reinterpret_cast<char*>(data.data()), data_size)) {
        break;
      }
      auto node = codec.decode(data.data(), data.size());
      if (!node) {
        continue;
      }
      runtime::Annotations::NodeKey key(name, static_cast<runtime::Annotations::NodeKey::NodeKeyType>(fields[0]), fields[1]);
      static_cast<SubTreePopulation*>(this->population)->add_subtree(node, key, (fields[2] + 1) / 2, (fields[3] + 1) / 2);
    }
    return true;
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
