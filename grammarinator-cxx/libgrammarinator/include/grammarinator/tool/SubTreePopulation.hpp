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
#include "../util/random.hpp"

#include <xxhash.h>

#include <algorithm>
#include <cassert>
#include <climits>
#include <cstdint>
#include <functional>
#include <map>
#include <ranges>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace grammarinator {
namespace tool {

class SubTreePopulation : public runtime::Population {
private:
  // The interned nodes of a type, with the sums of their selection weights
  // kept in a Fenwick tree, so that both changing the weight of a node and
  // drawing a node by weight take logarithmic time.
  struct Candidates {
    std::vector<runtime::Rule*> nodes;
    // sums[i] is the sum of the weights of the nodes in positions
    // [i - lowbit(i), i) (indexing sums from 1).
    std::vector<double> sums{0.0};

    static size_t lowbit(size_t i) { return i & -i; }

    // Sum of the weights of the first n nodes.
    double prefix_sum(size_t n) const {
      double sum = 0.0;
      for (; n > 0; n -= lowbit(n))
        sum += sums[n];
      return sum;
    }

    // Append a node with the given weight.
    void add(runtime::Rule* node, double weight) {
      nodes.push_back(node);
      size_t i = nodes.size();
      sums.push_back(prefix_sum(i - 1) - prefix_sum(i - lowbit(i)) + weight);
    }

    // Change the weight of the node at position pos by delta.
    void change_weight(size_t pos, double delta) {
      for (size_t i = pos + 1; i < sums.size(); i += lowbit(i))
        sums[i] += delta;
    }

    // Draw a node by weight.
    runtime::Rule* draw() const {
      double r = util::random_real(0.0, prefix_sum(nodes.size()));
      // The first node at which the sum of the weights reaches r (the last
      // one, if rounding errors let r exceed the sum of all the weights).
      auto positions = std::views::iota(size_t{0}, nodes.size() - 1);
      return nodes[*std::ranges::partition_point(positions, [&](size_t pos) { return prefix_sum(pos + 1) < r; })];
    }
  };

  struct RuleData {
    XXH64_hash_t hash{};
    runtime::Annotations::NodeKey key{""};
    runtime::RuleSize size{};
    int refcount{0};
    size_t pos{0};  // position among the candidates of the node's type
  };

  std::unordered_map<const runtime::Rule*, RuleData> rule_data_;
  std::vector<runtime::Rule*> nodes_;
  std::unordered_map<XXH64_hash_t, runtime::Rule*> node_by_hash_;
  std::map<runtime::Annotations::NodeKey, Candidates> nodes_by_name_;

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
        // Alternatives do not store the rule they belong to, so take it from their key.
        const auto& key = rule_data_[node].key;
        XXH64_update(&st, key.name.data(), key.name.size());
        const auto* a = static_cast<const runtime::UnparserRuleAlternative*>(node);
        XXH64_update(&st, &a->alt_idx, sizeof(a->alt_idx));
        XXH64_update(&st, &a->idx, sizeof(a->idx));
      } else if (node->type == runtime::Rule::UnparserRuleQuantifierType) {
        // Quantifiers do not store the rule they belong to, so take it from their key.
        const auto& key = rule_data_[node].key;
        XXH64_update(&st, key.name.data(), key.name.size());
        const auto* q = static_cast<const runtime::UnparserRuleQuantifier*>(node);
        XXH64_update(&st, &q->idx, sizeof(q->idx));
        XXH64_update(&st, &q->start, sizeof(q->start));
        int stop_enc = (q->stop == INT_MAX ? -1 : q->stop);
        XXH64_update(&st, &stop_enc, sizeof(stop_enc));
      } else if (node->type == runtime::Rule::UnparserRuleQuantifiedType) {
        // Quantified nodes store neither the rule nor the quantifier they belong to, so take both from their key.
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
      auto& data = rule_data_.at(node);
      double old_weight = weight(data);
      data.refcount++;
      nodes_by_name_.at(data.key).change_weight(data.pos, weight(data) - old_weight);

      if (node->type != runtime::Rule::UnlexerRuleType)
        for (auto* child : static_cast<const runtime::ParentRule*>(node)->children)
          dfs(child);
    };
    dfs(root);
  }

  // Selection weight of a node, preferring the nodes that are shared by fewer
  // trees.
  static double weight(const RuleData& data) {
    return 1.0 / double(data.refcount);
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

    auto& data = rule_data_.at(node);
    data.refcount = 1;
    nodes_.push_back(node);
    node_by_hash_[hash] = node;
    auto& candidates = nodes_by_name_[data.key];
    data.pos = candidates.nodes.size();
    candidates.add(node, weight(data));

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

    // Keys are needed by the hashes.
    runtime::Annotations annot(root);
    for (auto& [key, nodes] : annot.nodes_by_name()) {
      for (auto node : nodes)
        rule_data_[node].key = key;
    }
    collect_hashes(root);
    for (auto& [node, info] : annot.node_info()) {
      rule_data_.at(node).size.depth = info.depth;
      rule_data_.at(node).size.tokens = info.tokens;
    }

    intern_node(root);
  }

  runtime::Individual* select_individual(runtime::Individual* recipient = nullptr) override {
    assert(false);
    return new runtime::Individual(nodes_[util::random_int<size_t>(0, nodes_.size() - 1)]->clone());
  }

  runtime::Individual* select_by_type(runtime::Annotations::NodeKey type_name, int max_depth, int max_tokens) {
    // The budgets are negative if the recipient tree is already over the limits.
    if (max_depth < 0 || max_tokens < 0)
      return nullptr;
    auto it = nodes_by_name_.find(type_name);
    if (it == nodes_by_name_.end())
      return nullptr;
    const auto& candidates = it->second;
    const auto& candidate_nodes = candidates.nodes;

    // Check whether a candidate stays within the recipient's size limits.
    auto fits = [max_depth, max_tokens](const RuleData& data) {
      return data.size.depth <= max_depth && data.size.tokens <= max_tokens;
    };

    // Draw a candidate by weight and accept it if it fits. This draws from the
    // fitting candidates with the same distribution as the scans below, but
    // without visiting all the candidates. The scans are only needed if none
    // of a few draws fit.
    for (int i = 0; i < 8; ++i) {
      auto* node = candidates.draw();
      if (fits(rule_data_.at(node)))
        return new runtime::Individual(node->clone());
    }

    double total_w = 0.0;
    for (auto* node : candidate_nodes) {
      const auto& data = rule_data_.at(node);
      if (fits(data))
        total_w += weight(data);
    }
    if (total_w <= 0.0)
      return nullptr;

    double r = util::random_real(0.0, total_w);
    double acc = 0.0;
    for (auto* node : candidate_nodes) {
      const auto& data = rule_data_.at(node);
      if (!fits(data))
        continue;
      acc += weight(data);
      if (acc >= r)
        return new runtime::Individual(node->clone());
    }

    for (auto* node : candidate_nodes) {
      const auto& data = rule_data_.at(node);
      if (fits(data))
        return new runtime::Individual(node->clone());
    }

    return nullptr;
  }
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_SUBTREEPOPULATION_HPP
