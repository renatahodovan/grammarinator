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
#include <cassert>
#include <format>
#include <map>
#include <memory>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
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

  // The keyed nodes of a tree, by the pre-order positions of the nodes.
  using KeyPositions = std::vector<std::pair<NodeKey, std::vector<size_t>>>;
  struct PreorderKeys {
    KeyPositions nodes;
    KeyPositions rules;
    KeyPositions quants;
  };

  // The annotations of the tree of root_ by the pre-order positions of its
  // nodes, which apply to all the unchanged clones of the tree as well (built
  // on demand, when a clone needs them).
  std::unique_ptr<PreorderKeys> preorder_keys_{};
  std::vector<NodeInfo> preorder_info_{};

  // The annotations of the tree that the tree of root_ is an unchanged clone
  // of (if any).
  Annotations* source_{};
  // The nodes of the tree of root_ in pre-order (built on demand).
  std::vector<Rule*> preorder_{};

public:
  explicit Annotations(Rule* root) : root_(root) { }
  // If root is a clone of the tree of source (and the tree of source has not
  // changed since), the annotations are taken from source by the pre-order
  // positions of the nodes instead of being collected again, which is cheaper
  // if source is cloned repeatedly.
  Annotations(Rule* root, Annotations& source) : root_(root), source_(&source) { }
  Annotations(const Annotations& other) = delete;
  Annotations& operator=(const Annotations& other) = delete;
  Annotations(Annotations&& other) = delete;
  Annotations& operator=(Annotations&& other) = delete;
  ~Annotations() = default;

  auto& nodes_by_name() {
    if (!nodes_collected_) {
      if (source_) {
        take_keys(nodes_by_name_, source_->preorder_keys().nodes);
      } else {
        collect_nodes(root_, nullptr);
      }
      nodes_collected_ = true;
    }
    return nodes_by_name_;
  }

  auto& rules_by_name() {
    if (!rules_collected_) {
      if (source_) {
        take_keys(rules_by_name_, source_->preorder_keys().rules);
      } else {
        collect_rules(root_);
      }
      rules_collected_ = true;
    }
    return rules_by_name_;
  }

  auto& quants_by_name() {
    if (!quants_collected_) {
      if (source_) {
        take_keys(quants_by_name_, source_->preorder_keys().quants);
      } else {
        collect_quants(root_, nullptr);
      }
      quants_collected_ = true;
    }
    return quants_by_name_;
  }

  auto& node_info() {
    if (node_info_.empty()) {
      if (source_) {
        take_info(source_->preorder_info());
      } else {
        collect_info(root_, 0);
      }
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
    preorder_keys_.reset();
    preorder_info_.clear();
    source_ = nullptr;
    preorder_.clear();
  }

private:
  const std::vector<Rule*>& preorder() {
    if (preorder_.empty()) {
      std::vector<Rule*> worklist{root_};
      while (!worklist.empty()) {
        Rule* node = worklist.back();
        worklist.pop_back();
        preorder_.push_back(node);
        if (node->type != Rule::UnlexerRuleType) {
          const auto& children = static_cast<ParentRule*>(node)->children;
          worklist.insert(worklist.end(), children.rbegin(), children.rend());
        }
      }
    }
    return preorder_;
  }

  const PreorderKeys& preorder_keys() {
    if (!preorder_keys_) {
      const auto& nodes = preorder();
      std::unordered_map<Rule*, size_t> positions;
      positions.reserve(nodes.size());
      for (size_t i = 0; i < nodes.size(); ++i) {
        positions.emplace(nodes[i], i);
      }

      auto key_positions = [&](const std::map<NodeKey, std::vector<Rule*>>& keyed_nodes) {
        KeyPositions result;
        result.reserve(keyed_nodes.size());
        for (const auto& [key, key_nodes] : keyed_nodes) {
          auto& key_node_positions = result.emplace_back(key, std::vector<size_t>()).second;
          key_node_positions.reserve(key_nodes.size());
          for (auto node : key_nodes) {
            key_node_positions.push_back(positions.at(node));
          }
        }
        return result;
      };

      preorder_keys_ = std::make_unique<PreorderKeys>();
      preorder_keys_->nodes = key_positions(nodes_by_name());
      preorder_keys_->rules = key_positions(rules_by_name());
      preorder_keys_->quants = key_positions(quants_by_name());
    }
    return *preorder_keys_;
  }

  const std::vector<NodeInfo>& preorder_info() {
    if (preorder_info_.empty()) {
      const auto& info = node_info();
      const auto& nodes = preorder();
      preorder_info_.reserve(nodes.size());
      for (auto node : nodes) {
        preorder_info_.push_back(info.at(node));
      }
    }
    return preorder_info_;
  }

  void take_keys(std::map<NodeKey, std::vector<Rule*>>& keyed_nodes, const KeyPositions& source_positions) {
    const auto& nodes = preorder();
    for (const auto& [key, key_node_positions] : source_positions) {
      auto& key_nodes = keyed_nodes.emplace_hint(keyed_nodes.end(), key, std::vector<Rule*>())->second;
      key_nodes.reserve(key_node_positions.size());
      for (auto pos : key_node_positions) {
        key_nodes.push_back(nodes[pos]);
      }
    }
  }

  void take_info(const std::vector<NodeInfo>& source_info) {
    const auto& nodes = preorder();
    assert(nodes.size() == source_info.size());
    node_info_.reserve(nodes.size());
    for (size_t i = 0; i < nodes.size(); ++i) {
      node_info_.emplace(nodes[i], source_info[i]);
    }
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
