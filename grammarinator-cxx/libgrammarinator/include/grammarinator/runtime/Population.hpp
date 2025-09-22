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

public:
  explicit Annotations(Rule* root) : root_(root) { }
  Annotations(const Annotations& other) = delete;
  Annotations& operator=(const Annotations& other) = delete;
  Annotations(Annotations&& other) = delete;
  Annotations& operator=(Annotations&& other) = delete;
  ~Annotations() = default;

  auto& nodes_by_name() {
    if (nodes_by_name_.empty()) {
      collect_nodes(root_, nullptr);
    }
    return nodes_by_name_;
  }

  auto& rules_by_name() {
    if (rules_by_name_.empty()) {
      collect_rules(root_);
    }
    return rules_by_name_;
  }

  auto& quants_by_name() {
    if (quants_by_name_.empty()) {
      collect_quants(root_, nullptr);
    }
    return quants_by_name_;
  }

  auto& node_info() {
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
  }

private:
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

protected:
  UnparserRule* root_;

public:
  explicit Individual(Rule* root = nullptr, bool delete_root = true)
      : root_(new UnparserRule("<ROOT>")), delete_root_(delete_root) {
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

  Annotations* annotations() {
    if (!annot_) {
      annot_ = new Annotations(root());
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
