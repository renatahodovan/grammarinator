// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_POPULATION_HPP
#define GRAMMARINATOR_RUNTIME_POPULATION_HPP

#include "Rule.hpp"

#include <algorithm>
#include <array>
#include <cassert>
#include <format>
#include <map>
#include <string>
#include <tuple>
#include <unordered_map>
#include <vector>

namespace grammarinator {
namespace runtime {

class Annotations {
public:
  struct NodeKey {
    enum NodeKeyType { RuleKey, QuantifiedKey, QuantifierKey, AlternativeKey };

    std::string name;
    NodeKeyType type;
    int idx;

    explicit NodeKey(const std::string& name) : name(name), type(RuleKey), idx() { }
    NodeKey(const std::string& name, NodeKeyType type, int idx) : name(name), type(type), idx(idx) { }

    explicit NodeKey(const Rule* node, const std::string& name = "") : name(name.empty() ? node->rule_name() : name), idx() {
      switch (node->type) {
      case Rule::UnparserRuleType:
      case Rule::UnlexerRuleType:
        type = RuleKey;
        break;
      case Rule::UnparserRuleAlternativeType:
        type = AlternativeKey;
        idx = static_cast<const UnparserRuleAlternative*>(node)->alt_idx;
        break;
      case Rule::UnparserRuleQuantifierType:
        type = QuantifierKey;
        idx = static_cast<const UnparserRuleQuantifier*>(node)->idx;
        break;
      case Rule::UnparserRuleQuantifiedType:
        type = QuantifiedKey;
        idx = static_cast<const UnparserRuleQuantifier*>(node->parent)->idx;
        break;
      default:
        assert(false);
      }
    }

    NodeKey(const NodeKey& other) = default;
    NodeKey& operator=(const NodeKey& other) = default;
    NodeKey(NodeKey&& other) = default;
    NodeKey& operator=(NodeKey&& other) = default;
    ~NodeKey() = default;

    auto operator<=>(const NodeKey& other) const = default;

    std::string format() const {
      if (type == QuantifierKey) {
        return std::format("\"{}\", q, {}", name, idx);
      } else if (type == QuantifiedKey) {
        return std::format("\"{}\", qd, {}", name, idx);
      } else if (type == AlternativeKey) {
        return std::format("\"{}\", a, {}", name, idx);
      } else {
        return std::format("\"{}\"", name);
      }
    }
  };

  struct NodeInfo {
    int level;
    int depth;
    int tokens;
  };

private:
  Rule* root_;
  std::map<NodeKey, std::vector<Rule*>> nodes_by_name_{};
  std::map<NodeKey, std::vector<Rule*>> rules_by_name_{};
  std::map<NodeKey, std::vector<Rule*>> quants_by_name_{};
  std::unordered_map<Rule*, NodeInfo> node_info_{};
  bool nodes_collected_{};
  bool rules_collected_{};
  bool quants_collected_{};
  // The annotations of the tree that the tree of root_ is an unchanged clone
  // of, to take the keyed nodes from (until they are taken).
  Annotations* source_{};
  Annotations* info_source_{};
  // The keys of the nodes of the tree in pre-order, as indices into
  // nodes_by_name_, rules_by_name_, and quants_by_name_ (-1: not keyed).
  std::vector<std::array<int, 3>> key_indices_{};
  std::vector<NodeInfo> preorder_info_{};
  std::vector<Rule*> preorder_nodes_{};

public:
  explicit Annotations(Rule* root) : root_(root) { }
  // If root is a clone of the tree of source (and the tree of source has not
  // changed since), the keyed nodes are taken from source instead of being
  // collected again, which is cheaper if source is cloned repeatedly.
  Annotations(Rule* root, Annotations& source) : root_(root), source_(&source), info_source_(&source) { }
  Annotations(const Annotations& other) = delete;
  Annotations& operator=(const Annotations& other) = delete;
  Annotations(Annotations&& other) = delete;
  Annotations& operator=(Annotations&& other) = delete;
  ~Annotations() = default;

  auto& nodes_by_name() {
    if (source_) {
      take_keys();
    }
    if (!nodes_collected_) {
      collect_nodes(root_, nullptr);
      nodes_collected_ = true;
    }
    return nodes_by_name_;
  }

  auto& rules_by_name() {
    if (source_) {
      take_keys();
    }
    if (!rules_collected_) {
      collect_rules(root_);
      rules_collected_ = true;
    }
    return rules_by_name_;
  }

  auto& quants_by_name() {
    if (source_) {
      take_keys();
    }
    if (!quants_collected_) {
      collect_quants(root_, nullptr);
      quants_collected_ = true;
    }
    return quants_by_name_;
  }

  std::unordered_map<Rule*, NodeInfo>& node_info() {
    if (info_source_) {
      auto* source = info_source_;
      info_source_ = nullptr;
      if (source->preorder_info_.empty()) {
        const auto& info = source->node_info();
        const auto& nodes = source->preorder();
        source->preorder_info_.reserve(nodes.size());
        for (auto node : nodes) {
          source->preorder_info_.push_back(info.at(node));
        }
      }
      const auto& nodes = preorder();
      assert(nodes.size() == source->preorder_info_.size());
      node_info_.reserve(nodes.size());
      for (size_t i = 0; i < nodes.size(); ++i) {
        node_info_.emplace(nodes[i], source->preorder_info_[i]);
      }
    }
    if (node_info_.empty()) {
      collect_info(root_, 0);
    }
    return node_info_;
  }

  std::vector<Rule*> nodes() {
    std::vector<Rule*> result;
    for (auto& [rule_name, nodes] : nodes_by_name()) {
      for (auto node : nodes)
        result.push_back(node);
    }
    return result;
  }

  std::vector<Rule*> rules() {
    std::vector<Rule*> result;
    for (auto& [rule_name, nodes] : rules_by_name()) {
      for (auto node : nodes)
        result.push_back(node);
    }
    return result;
  }

  std::vector<Rule*> quants() {
    std::vector<Rule*> result;
    for (auto& [rule_name, nodes] : quants_by_name()) {
      for (auto node : nodes)
        result.push_back(node);
    }
    return result;
  }


  void reset() {
    nodes_by_name_.clear();
    rules_by_name_.clear();
    quants_by_name_.clear();
    node_info_.clear();
    nodes_collected_ = rules_collected_ = quants_collected_ = false;
    source_ = info_source_ = nullptr;
    key_indices_.clear();
    preorder_info_.clear();
    preorder_nodes_.clear();
  }

private:
  // Reuse the node order when transferring both keys and size annotations.
  const std::vector<Rule*>& preorder() {
    if (!preorder_nodes_.empty()) {
      return preorder_nodes_;
    }
    auto& nodes = preorder_nodes_;
    std::vector<Rule*> worklist{root_};
    while (!worklist.empty()) {
      Rule* node = worklist.back();
      worklist.pop_back();
      nodes.push_back(node);
      if (node->type != Rule::UnlexerRuleType) {
        const auto& children = static_cast<ParentRule*>(node)->children;
        worklist.insert(worklist.end(), children.rbegin(), children.rend());
      }
    }
    return nodes;
  }

  const std::vector<std::array<int, 3>>& key_indices() {
    if (key_indices_.empty()) {
      const auto& nodes = preorder();
      std::unordered_map<Rule*, size_t> positions;
      positions.reserve(nodes.size());
      for (size_t i = 0; i < nodes.size(); ++i) {
        positions[nodes[i]] = i;
      }
      key_indices_.assign(nodes.size(), {-1, -1, -1});
      std::map<NodeKey, std::vector<Rule*>>* maps[] = {&nodes_by_name(), &rules_by_name(), &quants_by_name()};
      for (int m = 0; m < 3; ++m) {
        int k = 0;
        for (const auto& [key, keyed_nodes] : *maps[m]) {
          for (auto node : keyed_nodes) {
            key_indices_[positions.at(node)][m] = k;
          }
          k++;
        }
      }
    }
    return key_indices_;
  }

  // Take the keyed nodes from source: the nodes at the same pre-order
  // positions get the same keys, in the same order.
  void take_keys() {
    Annotations* source = source_;
    source_ = nullptr;
    const auto& indices = source->key_indices();
    std::map<NodeKey, std::vector<Rule*>>* source_maps[] = {&source->nodes_by_name_, &source->rules_by_name_, &source->quants_by_name_};
    std::map<NodeKey, std::vector<Rule*>>* maps[] = {&nodes_by_name_, &rules_by_name_, &quants_by_name_};
    std::vector<std::vector<Rule*>*> keyed_nodes[3];
    for (int m = 0; m < 3; ++m) {
      for (const auto& [key, source_nodes] : *source_maps[m]) {
        auto it = maps[m]->emplace_hint(maps[m]->end(), key, std::vector<Rule*>());
        it->second.reserve(source_nodes.size());
        keyed_nodes[m].push_back(&it->second);
      }
    }
    const auto& nodes = preorder();
    assert(nodes.size() == indices.size());
    for (size_t i = 0; i < nodes.size(); ++i) {
      for (int m = 0; m < 3; ++m) {
        if (indices[i][m] >= 0) {
          keyed_nodes[m][indices[i][m]]->push_back(nodes[i]);
        }
      }
    }
    nodes_collected_ = rules_collected_ = quants_collected_ = true;
  }

  void collect_nodes(Rule* current, std::string* current_rule_name) {
    if (current->type == Rule::UnparserRuleType) {
      current_rule_name = &current->name;
    }
    if ((current->type == Rule::UnlexerRuleType || current->type == Rule::UnparserRuleType) &&
        current != root_ &&
        current->name != "<INVALID>" && current->name != "<ROOT>" &&
        (current->type != Rule::UnlexerRuleType || !static_cast<UnlexerRule*>(current)->immutable)) {
      nodes_by_name_[NodeKey(current->name)].push_back(current);
    } else if ((current->type == Rule::UnparserRuleAlternativeType ||
                current->type == Rule::UnparserRuleQuantifierType ||
                current->type == Rule::UnparserRuleQuantifiedType) &&
               current_rule_name) {
      nodes_by_name_[NodeKey(current, *current_rule_name)].push_back(current);
    }

    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_nodes(child, current_rule_name);
      }
    }
  }

  void collect_rules(Rule* current) {
    if ((current->type == Rule::UnlexerRuleType || current->type == Rule::UnparserRuleType) &&
        current != root_ &&
        current->name != "<INVALID>" && current->name != "<ROOT>" &&
        (current->type != Rule::UnlexerRuleType || !static_cast<UnlexerRule*>(current)->immutable)) {
      rules_by_name_[NodeKey(current->name)].push_back(current);
    }

    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_rules(child);
      }
    }
  }

  void collect_quants(Rule* current, std::string* current_rule_name) {
    if (current->type == Rule::UnparserRuleType) {
      current_rule_name = &current->name;
    } else if (current->type == Rule::UnparserRuleQuantifierType && current_rule_name) {
      quants_by_name_[NodeKey(current, *current_rule_name)].push_back(current);
    }

    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_quants(child, current_rule_name);
      }
    }
  }

  std::tuple<int, int> collect_info(Rule* current, int level) {
    int depth = 0;
    int tokens = 0;
    if (current->type != Rule::UnlexerRuleType) {
      bool current_is_unparser_rule = current->type == Rule::UnparserRuleType;
      int child_level = level;
      if (current_is_unparser_rule) {
        child_level++;
      }
      for (auto child : static_cast<ParentRule*>(current)->children) {
        auto [child_depth, child_tokens] = collect_info(child, child_level);
        depth = std::max(depth, child_depth);
        tokens += child_tokens;
      }
      if (current_is_unparser_rule) {
        depth++;
      }
    } else {
      auto current_size = static_cast<UnlexerRule*>(current)->size;
      depth = current_size.depth;
      tokens = current_size.tokens;
    }
    node_info_[current] = {level, depth, tokens};
    return {depth, tokens};
  }
};

class Individual {
private:
  Annotations* annot_{};
  bool delete_root_;
  Annotations* source_;

protected:
  UnparserRule* root_;

public:
  // If the individual is a clone of the tree of source (and the tree of
  // source has not changed since), its annotations reuse those of source.
  explicit Individual(Rule* root = nullptr, bool delete_root = true, Annotations* source = nullptr)
      : root_(new UnparserRule("<ROOT>")), delete_root_(delete_root), source_(source) {
    if (root) {
      root_->add_child(root);
    }
  }
  Individual(const Individual& other) = delete;
  Individual& operator=(const Individual& other) = delete;
  Individual(Individual&& other) = delete;
  Individual& operator=(Individual&& other) = delete;

  virtual ~Individual() {
    delete annot_;

    if (!delete_root_ && root_->children.size() > 0)
      root_->children[0]->remove();
    delete root_;
  }

  virtual Rule* root() {
    assert(root_->children.size() <= 1);
    return root_->children.size() == 0 ? nullptr : root_->children[0];
  };

  virtual std::string name() const { return {}; }

  Annotations* annotations() {
    if (!annot_) {
      annot_ = source_ ? new Annotations(root(), *source_) : new Annotations(root());
    }
    return annot_;
  }
};

class Population {
public:
  Population() = default;
  Population(const Population& other) = delete;
  Population& operator=(const Population& other) = delete;
  Population(Population&& other) = delete;
  Population& operator=(Population&& other) = delete;
  virtual ~Population() = default;

  virtual bool empty() const = 0;
  virtual void add_individual(Rule* root, const std::string& path = "") = 0;
  virtual Individual* select_individual(Individual* recipient = nullptr) = 0;
};

} // namespace runtime
} // namespace grammarinator

template<>
struct std::formatter<grammarinator::runtime::Annotations::NodeKey> {
  template<class ParseContext>
  constexpr auto parse(ParseContext& ctx) {
    return ctx.begin();
  }

  template<class FmtContext>
  auto format(const grammarinator::runtime::Annotations::NodeKey& size, FmtContext& ctx) const {
    return std::format_to(ctx.out(), "{}", size.format());
  }
};

#endif // GRAMMARINATOR_RUNTIME_POPULATION_HPP
