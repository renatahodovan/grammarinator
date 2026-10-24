// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_SUBTREEPOPULATION_HPP
#define GRAMMARINATOR_SUBTREEPOPULATION_HPP

#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../runtime/WeightedModel.hpp"
#include "../util/random.hpp"

#include <xxhash.h>

#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdint>
#include <functional>
#include <map>
#include <string>
#include <tuple>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace grammarinator {
namespace tool {

class SubTreePopulation : public runtime::Population {
private:
  struct RuleData {
    XXH64_hash_t hash{};
    runtime::Annotations::NodeKey key{""};
    runtime::RuleSize size{};
    int refcount{0};
    bool self_embedding{false};  // the node has a descendant of the same rule
    int uses{0};  // number of emitted mutations that used the node
    int successes{0};  // number of those mutations that produced a new queue entry
  };

  std::unordered_map<const runtime::Rule*, RuleData> rule_data_;
  std::vector<runtime::Rule*> nodes_;
  std::unordered_map<XXH64_hash_t, runtime::Rule*> node_by_hash_;
  std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> nodes_by_name_;
  std::map<runtime::WeightedModel::AltMapKey, int> alt_counts_;

  static char encode_kind(runtime::Rule::RuleType t) {
    switch (t) {
      case runtime::Rule::UnlexerRuleType: return 'l';
      case runtime::Rule::UnparserRuleType: return 'p';
      case runtime::Rule::UnparserRuleAlternativeType: return 'a';
      case runtime::Rule::UnparserRuleQuantifiedType: return 'd';
      case runtime::Rule::UnparserRuleQuantifierType: return 'q';
      default: assert(false); return '?';
    }
  }

  XXH64_hash_t collect_hashes(const runtime::Rule* node) {
    XXH64_state_t st;
    XXH64_reset(&st, 0);

    const char kind = encode_kind(node->type);
    XXH64_update(&st, &kind, sizeof(kind));

    if (node->type == runtime::Rule::UnlexerRuleType) {
      const auto* l = static_cast<const runtime::UnlexerRule*>(node);
      XXH64_update(&st, l->name.data(), l->name.size());
      XXH64_update(&st, l->src.data(), l->src.size());
      XXH64_update(&st, &l->size.depth, sizeof(l->size.depth));
      XXH64_update(&st, &l->size.tokens, sizeof(l->size.tokens));
      XXH64_update(&st, &l->immutable, sizeof(l->immutable));
    } else {
      if (node->type == runtime::Rule::UnparserRuleType) {
        XXH64_update(&st, node->name.data(), node->name.size());
      } else if (node->type == runtime::Rule::UnparserRuleAlternativeType) {
        const auto* a = static_cast<const runtime::UnparserRuleAlternative*>(node);
        XXH64_update(&st, &a->alt_idx, sizeof(a->alt_idx));
        XXH64_update(&st, &a->idx, sizeof(a->idx));
      } else if (node->type == runtime::Rule::UnparserRuleQuantifierType) {
        const auto* q = static_cast<const runtime::UnparserRuleQuantifier*>(node);
        XXH64_update(&st, &q->idx, sizeof(q->idx));
        XXH64_update(&st, &q->start, sizeof(q->start));
        int stop_enc = (q->stop == INT_MAX ? -1 : q->stop);
        XXH64_update(&st, &stop_enc, sizeof(stop_enc));
      }
      if (node->type != runtime::Rule::UnparserRuleType) {
        // Alternative, quantifier and quantified nodes do not store the rule
        // (and quantified nodes not even the quantifier) they belong to, so
        // their key is hashed to keep structurally identical nodes of
        // different contexts apart.
        const auto& key = rule_data_[node].key;
        XXH64_update(&st, key.name.data(), key.name.size());
        XXH64_update(&st, &key.idx, sizeof(key.idx));
      }

      const char open = '(', comma = ',', close = ')';
      XXH64_update(&st, &open, 1);
      for (auto* child : static_cast<const runtime::ParentRule*>(node)->children) {
        XXH64_hash_t hash = collect_hashes(child);
        XXH64_update(&st, &hash, sizeof(hash));
        XXH64_update(&st, &comma, 1);
      }
      XXH64_update(&st, &close, 1);
    }

    auto hash = XXH64_digest(&st);
    rule_data_[node].hash = hash;
    return hash;
  }

  void erase_data(runtime::Rule* node) {
    rule_data_.erase(node);
    if (node->type != runtime::Rule::UnlexerRuleType)
      for (auto* child : static_cast<const runtime::ParentRule*>(node)->children)
        erase_data(child);
  }

  void bump_refcounts(runtime::Rule* root) {
    if (!root) return;

    std::unordered_set<const runtime::Rule*> seen;
    std::function<void(runtime::Rule*)> dfs = [&](runtime::Rule* node) {
      if (!node) return;
      if (!seen.insert(node).second) return;
      rule_data_.at(node).refcount++;

      if (node->type != runtime::Rule::UnlexerRuleType)
        for (auto* child : static_cast<const runtime::ParentRule*>(node)->children)
          dfs(child);
    };
    dfs(root);
  }

  // Key of an alternative node in the alternative counts.
  static runtime::WeightedModel::AltMapKey alt_key(const runtime::Rule* node, const runtime::Annotations::NodeKey& key) {
    const auto* alt = static_cast<const runtime::UnparserRuleAlternative*>(node);
    return {key.name, alt->alt_idx, alt->idx};
  }

  // Compute the keys, hashes, sizes and self-embedding flags of the nodes of
  // a new tree. The key of the root has to be given, as it cannot be computed
  // from the tree itself (and if the root is not a rule node, its descendants
  // inherit its rule name).
  void annotate(runtime::Rule* root, const runtime::Annotations::NodeKey& root_key = runtime::Annotations::NodeKey("")) {
    // Keys are needed by the hashes.
    runtime::Annotations annot(root, root_key.name);
    rule_data_[root].key = root_key;
    for (auto& [key, nodes] : annot.nodes_by_name()) {
      for (auto node : nodes)
        rule_data_[node].key = key;
    }
    collect_hashes(root);
    for (auto& [node, info] : annot.node_info()) {
      rule_data_.at(node).size.depth = info.depth;
      rule_data_.at(node).size.tokens = info.tokens;
      if (node->type == runtime::Rule::UnparserRuleType) {
        for (runtime::Rule* parent = node->parent; parent; parent = parent->parent) {
          if (parent->name == node->name) {
            rule_data_.at(parent).self_embedding = true;
          }
        }
      }
    }
  }

  // Selection weight of a node: the expected success rate of the node
  // (estimated with a uniform prior, so that unused nodes are also tried),
  // preferring the nodes that are shared by fewer trees.
  double weight(const RuleData& data) const {
    return (data.successes + 1.0) / (data.uses + 2.0) / double(data.refcount);
  }

  runtime::Rule* intern_node(runtime::Rule* node) {
    const XXH64_hash_t hash = rule_data_.at(node).hash;

    auto it = node_by_hash_.find(hash);
    if (it != node_by_hash_.end()) {
      erase_data(node);
      delete node;

      bump_refcounts(it->second);
      return it->second;  // return the ptr to the "identical" node found among the previously interned nodes
    }

    rule_data_.at(node).refcount = 1;
    nodes_.push_back(node);
    node_by_hash_[hash] = node;
    nodes_by_name_[rule_data_.at(node).key].push_back(node);
    if (node->type == runtime::Rule::UnparserRuleAlternativeType) {
      alt_counts_[alt_key(node, rule_data_.at(node).key)]++;
    }

    if (node->type != runtime::Rule::UnlexerRuleType) {
      auto* parent = static_cast<runtime::ParentRule*>(node);
      for (size_t i = 0; i < parent->children.size(); ++i) {
        parent->children[i] = intern_node(parent->children[i]);
      }
    }
    return node;
  }

public:
  SubTreePopulation() = default;
  SubTreePopulation(const SubTreePopulation& other) = delete;
  SubTreePopulation& operator=(const SubTreePopulation& other) = delete;
  SubTreePopulation(SubTreePopulation&& other) = delete;
  SubTreePopulation& operator=(SubTreePopulation&& other) = delete;

  ~SubTreePopulation() override {
    for (auto* node : nodes_)
      if (node->type != runtime::Rule::UnlexerRuleType)
        static_cast<runtime::ParentRule*>(node)->children.clear();

    for (auto* node : nodes_)
      delete node;
  }

  bool empty() const override { return nodes_.size() == 0; }

  void add_individual(runtime::Rule* root, const std::string& path = "") override {
    if (!root) return;

    root = root->clone();
    annotate(root);
    intern_node(root);
  }

  runtime::Individual* select_individual(runtime::Individual* recipient = nullptr) override {
    assert(false);
    return new runtime::Individual(nodes_[util::random_int<size_t>(0, nodes_.size() - 1)]->clone());
  }

  // Add a subtree with known usage statistics (e.g., loaded from a previous
  // fuzz session) to the pool.
  void add_subtree(runtime::Rule* node, const runtime::Annotations::NodeKey& key, int successes, int uses) {
    annotate(node, key);
    node = intern_node(node);
    auto& data = rule_data_.at(node);
    data.successes += successes;
    data.uses += uses;
  }

  // The subtrees that were used most successfully, with their keys and usage
  // statistics.
  std::vector<std::tuple<runtime::Rule*, runtime::Annotations::NodeKey, int, int>> best_subtrees(size_t n) const {
    std::vector<std::tuple<runtime::Rule*, runtime::Annotations::NodeKey, int, int>> best;
    for (const auto& [node, data] : rule_data_) {
      if (data.successes > 0 && !data.key.name.empty()) {
        best.emplace_back(const_cast<runtime::Rule*>(node), data.key, data.successes, data.uses);
      }
    }
    std::sort(best.begin(), best.end(), [](const auto& a, const auto& b) {
      return std::get<2>(a) != std::get<2>(b) ? std::get<2>(a) > std::get<2>(b) : std::get<3>(a) < std::get<3>(b);
    });
    if (best.size() > n) {
      best.erase(best.begin() + n, best.end());
    }
    return best;
  }

  // Count a use for each of the subtrees with the given hashes.
  void record_uses(const std::vector<XXH64_hash_t>& hashes) {
    for (auto hash : hashes) {
      auto it = node_by_hash_.find(hash);
      if (it != node_by_hash_.end())
        rule_data_.at(it->second).uses++;
    }
  }

  // Count a success for each of the subtrees with the given hashes.
  void record_successes(const std::vector<XXH64_hash_t>& hashes) {
    for (auto hash : hashes) {
      auto it = node_by_hash_.find(hash);
      if (it != node_by_hash_.end())
        rule_data_.at(it->second).successes++;
    }
  }

  // Number of distinct subtrees in the pool per (rule name, alternation index, alternative index).
  const std::map<runtime::WeightedModel::AltMapKey, int>& alt_counts() const { return alt_counts_; }

  // Select a subtree of the given type within the size limits (and
  // optionally, only from those that embed their own rule). The hash of the
  // selected subtree is stored in hash, if given, so that its usage can be
  // recorded.
  runtime::Individual* select_by_type(runtime::Annotations::NodeKey type_name, size_t max_depth, size_t max_tokens, bool self_embedding_only = false,
                                      XXH64_hash_t* hash = nullptr) {
    auto it = nodes_by_name_.find(type_name);
    if (it == nodes_by_name_.end())
      return nullptr;
    const auto& candidate_nodes = it->second;

    auto fits = [&](runtime::Rule* node) {
      const auto& data = rule_data_.at(node);
      return data.size.depth <= max_depth && data.size.tokens <= max_tokens && (!self_embedding_only || data.self_embedding);
    };

    auto select = [&](runtime::Rule* node) {
      if (hash)
        *hash = rule_data_.at(node).hash;
      return new runtime::Individual(node->clone());
    };

    double total_w = 0.0;
    for (auto* node : candidate_nodes)
      if (fits(node))
        total_w += weight(rule_data_.at(node));
    if (total_w <= 0.0)
      return nullptr;

    double r = util::random_real(0.0, total_w);
    double acc = 0.0;
    for (auto* node : candidate_nodes) {
      if (!fits(node))
        continue;
      acc += weight(rule_data_.at(node));
      if (acc >= r)
        return select(node);
    }

    for (auto* node : candidate_nodes)
      if (rule_data_.at(node).size.tokens <= max_tokens && (!self_embedding_only || rule_data_.at(node).self_embedding))
        return select(node);

    return nullptr;
  }
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_SUBTREEPOPULATION_HPP
