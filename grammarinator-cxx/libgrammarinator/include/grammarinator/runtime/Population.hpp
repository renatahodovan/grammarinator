// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_POPULATION_HPP
#define GRAMMARINATOR_RUNTIME_POPULATION_HPP

#include "Rule.hpp"

#include <algorithm>
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
    enum NodeKeyType { RuleKey, QuantifierKey, AlternativeKey };

    std::string name;
    NodeKeyType type;
    int idx;

    explicit NodeKey(const std::string& name) : name(name), type(RuleKey), idx() { }
    NodeKey(const std::string& name, NodeKeyType type, int idx) : name(name), type(type), idx(idx) { }
    NodeKey(const NodeKey& other) = default;
    NodeKey& operator=(const NodeKey& other) = default;
    NodeKey(NodeKey&& other) = default;
    NodeKey& operator=(NodeKey&& other) = default;
    ~NodeKey() = default;

    auto operator<=>(const NodeKey& other) const = default;

    std::string format() const {
      if (type == QuantifierKey) {
        return std::format("\"{}\", q, {}", name, idx);
      } else if (type == AlternativeKey) {
        return std::format("\"{}\", a, ", name, idx);
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
  std::map<NodeKey, std::vector<Rule*>> rules_by_name_{};
  std::map<NodeKey, std::vector<Rule*>> alts_by_name_{};
  std::map<NodeKey, std::vector<Rule*>> quants_by_name_{};
  std::unordered_map<Rule*, NodeInfo> node_info_{};

public:
  explicit Annotations(Rule* root) : root_(root) { }
  Annotations(const Annotations& other) = delete;
  Annotations& operator=(const Annotations& other) = delete;
  Annotations(Annotations&& other) = delete;
  Annotations& operator=(Annotations&& other) = delete;
  ~Annotations() = default;

  auto& rules_by_name() {
    if (rules_by_name_.empty()) {
      collect_rules(root_);
    }
    return rules_by_name_;
  }

  auto& alts_by_name() {
    if (alts_by_name_.empty()) {
      collect_alts(root_, nullptr);
    }
    return alts_by_name_;
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

  std::vector<Rule*> rules() {
    std::vector<Rule*> result;
    for (auto& [rule_name, nodes] : rules_by_name()) {
      for (auto node : nodes)
        result.push_back(node);
    }
    return result;
  }

  std::vector<Rule*> alts() {
    std::vector<Rule*> result;
    for (auto& [rule_name, nodes] : alts_by_name()) {
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

/*
  // TODO: nodes() doesn't save its result, but returns it where it was requested.
  std::vector<Rule*> nodes(Rule* current) {
    std::vector<Rule*> result;
    std::vector<Rule*> worklist = {current};

    while (!worklist.empty()) {
      Rule* r = worklist.back();
      worklist.pop_back();
      if (r->name != "<ROOT>" && r->parent->name != "<ROOT>")
        result.push_back(r);
      if (r->type != Rule::UnlexerRuleType) {
        for (Rule* child : static_cast<ParentRule*>(r)->children) {
          worklist.push_back(child);
        }
      }
    }
    return result;
  }
*/

  void reset() {
    rules_by_name_.clear();
    alts_by_name_.clear();
    quants_by_name_.clear();
    node_info_.clear();
  }

private:
  void collect_rules(Rule* current) {
    if ((current->type == Rule::UnlexerRuleType || current->type == Rule::UnparserRuleType) &&
        current != root_ &&
        !current->name.empty() && current->name != "<INVALID>" && current->name != "<ROOT>" &&
        (current->type != Rule::UnlexerRuleType || !static_cast<UnlexerRule*>(current)->immutable)) {
        rules_by_name_[NodeKey(current->name)].push_back(current);
    }

    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_rules(child);
      }
    }
  }

  void collect_alts(Rule* current, std::string* current_rule_name) {
    if (current->type == Rule::UnparserRuleType) {
      current_rule_name = !current->name.empty() && current->name != "<INVALID>" ? &current->name : nullptr;
    } else if (current->type == Rule::UnparserRuleAlternativeType && current_rule_name) {
      alts_by_name_[NodeKey(*current_rule_name,
                            NodeKey::AlternativeKey,
                            static_cast<const UnparserRuleAlternative*>(current)->alt_idx)].push_back(current);
    }

    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_alts(child, current_rule_name);
      }
    }
  }

  void collect_quants(Rule* current, std::string* current_rule_name) {
    if (current->type == Rule::UnparserRuleType) {
      current_rule_name = !current->name.empty() && current->name != "<INVALID>" ? &current->name : nullptr;
    } if (current->type == Rule::UnparserRuleQuantifierType && current_rule_name) {
      quants_by_name_[NodeKey(*current_rule_name,
                              NodeKey::QuantifierKey,
                              static_cast<const UnparserRuleQuantifier*>(current)->idx)].push_back(current);
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
  Rule* root_;

public:
  explicit Individual(Rule* root = nullptr, bool delete_root = true) : root_(root), delete_root_(delete_root) { }
  Individual(const Individual& other) = delete;
  Individual& operator=(const Individual& other) = delete;
  Individual(Individual&& other) = delete;
  Individual& operator=(Individual&& other) = delete;

  virtual ~Individual() {
    delete annot_;

    if (delete_root_) {
      delete root_;
    }
  }

  virtual Rule* root() {
    return root_;
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
