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
#include <optional>
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

  // The annotations are collected in a pointer-free form first, where nodes
  // are identified by their pre-order positions in the tree. This form only
  // depends on the structure (and the contents) of the tree, so it is the same
  // for a tree and all its unchanged clones, and it is shared with the
  // annotations of the clones (it is immutable once collected).

  // The pointer-free annotations (collected on demand).
  std::shared_ptr<const std::map<NodeKey, std::vector<size_t>>> node_positions_;
  std::shared_ptr<const std::map<NodeKey, std::vector<size_t>>> rule_positions_;
  std::shared_ptr<const std::map<NodeKey, std::vector<size_t>>> quant_positions_;
  std::shared_ptr<const std::vector<NodeInfo>> info_positions_;
  // The nodes of the tree in pre-order (built on demand).
  std::vector<Rule*> preorder_{};

  // The annotations by node pointers, as exposed by the public API (built on
  // demand from the pointer-free annotations and the pre-order of the nodes).
  std::map<NodeKey, std::vector<Rule*>> nodes_by_name_{};
  std::map<NodeKey, std::vector<Rule*>> rules_by_name_{};
  std::map<NodeKey, std::vector<Rule*>> quants_by_name_{};
  std::unordered_map<Rule*, NodeInfo> node_info_{};
  bool nodes_collected_{};
  bool rules_collected_{};
  bool quants_collected_{};
  bool info_collected_{};

  // Both collectors visit the nodes in pre-order, so they can build the
  // pre-order list of the nodes as a by-product (if it does not exist yet).

  void collect_nodes(Rule* current, const std::string* current_rule_name,
                     std::optional<NodeKey::NodeKeyType> filter,
                     size_t& pos, bool build_preorder, std::map<NodeKey, std::vector<size_t>>& result) {
    if (build_preorder) {
      preorder_.push_back(current);
    }
    if (current->type == Rule::UnparserRuleType) {
      current_rule_name = &current->name;
    }
    if (current->type == Rule::UnlexerRuleType || current->type == Rule::UnparserRuleType) {
      if ((!filter || *filter == NodeKey::RuleKey) &&
          current != root_ &&
          current->name != "<INVALID>" && current->name != "<ROOT>" &&
          (current->type != Rule::UnlexerRuleType || !static_cast<UnlexerRule*>(current)->immutable)) {
        result[NodeKey(current->name)].push_back(pos);
      }
    } else if (current->type == Rule::UnparserRuleQuantifierType) {
      if ((!filter || *filter == NodeKey::QuantifierKey) &&
          current_rule_name) {
        result[NodeKey(current, *current_rule_name)].push_back(pos);
      }
    } else if (current->type == Rule::UnparserRuleAlternativeType ||
               current->type == Rule::UnparserRuleQuantifiedType) {
      if (!filter && current_rule_name) {
        result[NodeKey(current, *current_rule_name)].push_back(pos);
      }
    }
    pos++;

    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_nodes(child, current_rule_name, filter, pos, build_preorder, result);
      }
    }
  }

  std::tuple<int, int> collect_info(Rule* current, int level,
                                    bool build_preorder, std::vector<NodeInfo>& result) {
    if (build_preorder) {
      preorder_.push_back(current);
    }
    size_t pos = result.size();
    result.push_back({level, 0, 0});

    int depth = 0;
    int tokens = 0;
    if (current->type != Rule::UnlexerRuleType) {
      bool current_is_unparser_rule = current->type == Rule::UnparserRuleType;
      int child_level = current_is_unparser_rule ? level + 1 : level;
      for (auto child : static_cast<ParentRule*>(current)->children) {
        auto [child_depth, child_tokens] = collect_info(child, child_level, build_preorder, result);
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
    result[pos].depth = depth;
    result[pos].tokens = tokens;
    return {depth, tokens};
  }

  void collect_preorder(Rule* current) {
    preorder_.push_back(current);
    if (current->type != Rule::UnlexerRuleType) {
      for (auto child : static_cast<ParentRule*>(current)->children) {
        collect_preorder(child);
      }
    }
  }

  const auto& preorder() {
    if (preorder_.empty()) {
      collect_preorder(root_);
    }
    return preorder_;
  }

  auto filter_positions(NodeKey::NodeKeyType filter) {
    auto result = std::make_shared<std::map<NodeKey, std::vector<size_t>>>();
    for (const auto& entry : *node_positions_) {
      if (entry.first.type == filter) {
        result->emplace_hint(result->end(), entry);
      }
    }
    return result;
  }

  auto collect_positions(std::optional<NodeKey::NodeKeyType> filter = std::nullopt) {
    bool build_preorder = preorder_.empty();
    size_t pos = 0;
    auto result = std::make_shared<std::map<NodeKey, std::vector<size_t>>>();
    collect_nodes(root_, nullptr, filter, pos, build_preorder, *result);
    return result;
  }

  const auto& node_positions() {
    if (!node_positions_) {
      node_positions_ = collect_positions();
    }
    return node_positions_;
  }

  // The rules and quantifiers are subsets of the nodes: if those are already
  // known, they are filtered from them, otherwise they are collected (cheaper
  // than collecting all the nodes).

  const auto& rule_positions() {
    if (!rule_positions_) {
      rule_positions_ = node_positions_ ? filter_positions(NodeKey::RuleKey)
                                        : collect_positions(NodeKey::RuleKey);
    }
    return rule_positions_;
  }

  const auto& quant_positions() {
    if (!quant_positions_) {
      quant_positions_ = node_positions_ ? filter_positions(NodeKey::QuantifierKey)
                                         : collect_positions(NodeKey::QuantifierKey);
    }
    return quant_positions_;
  }

  const auto& info_positions() {
    if (!info_positions_) {
      bool build_preorder = preorder_.empty();
      auto result = std::make_shared<std::vector<NodeInfo>>();
      collect_info(root_, 0, build_preorder, *result);
      info_positions_ = std::move(result);
    }
    return info_positions_;
  }

  void materialize(std::map<NodeKey, std::vector<Rule*>>& named_nodes,
                   const std::map<NodeKey, std::vector<size_t>>& named_positions) {
    const auto& preorder_nodes = preorder();
    for (const auto& [name, positions] : named_positions) {
      auto& nodes = named_nodes.emplace_hint(named_nodes.end(), name, std::vector<Rule*>())->second;
      nodes.reserve(positions.size());
      for (auto pos : positions) {
        nodes.push_back(preorder_nodes[pos]);
      }
    }
  }

  static auto flatten(const std::map<NodeKey, std::vector<Rule*>>& named_nodes) {
    std::vector<Rule*> result;
    for (const auto& [name, nodes] : named_nodes) {
      result.insert(result.end(), nodes.begin(), nodes.end());
    }
    return result;
  }

public:
  explicit Annotations(Rule* root) : root_(root), node_positions_(), rule_positions_(), quant_positions_(), info_positions_() { }
  // Annotations of root, which must be an unchanged clone of the tree of other.
  // The pointer-free annotations are shared with other (and collected now if
  // other has not collected them yet), not collected again for root.
  Annotations(Rule* root, Annotations& other)
      : root_(root),
        node_positions_(other.node_positions()), rule_positions_(other.rule_positions()),
        quant_positions_(other.quant_positions()), info_positions_(other.info_positions()) {
    assert(root->equals(*other.root_));
  }
  Annotations(const Annotations& other) = delete;
  Annotations& operator=(const Annotations& other) = delete;
  Annotations(Annotations&& other) = delete;
  Annotations& operator=(Annotations&& other) = delete;
  ~Annotations() = default;

  auto& nodes_by_name() {
    if (!nodes_collected_) {
      materialize(nodes_by_name_, *node_positions());
      nodes_collected_ = true;
    }
    return nodes_by_name_;
  }

  auto& rules_by_name() {
    if (!rules_collected_) {
      materialize(rules_by_name_, *rule_positions());
      rules_collected_ = true;
    }
    return rules_by_name_;
  }

  auto& quants_by_name() {
    if (!quants_collected_) {
      materialize(quants_by_name_, *quant_positions());
      quants_collected_ = true;
    }
    return quants_by_name_;
  }

  auto& node_info() {
    if (!info_collected_) {
      const auto& info = *info_positions();
      const auto& nodes = preorder();
      node_info_.reserve(nodes.size());
      for (size_t i = 0; i < nodes.size(); ++i) {
        node_info_.emplace(nodes[i], info[i]);
      }
      info_collected_ = true;
    }
    return node_info_;
  }

  auto nodes() { return flatten(nodes_by_name()); }
  auto rules() { return flatten(rules_by_name()); }
  auto quants() { return flatten(quants_by_name()); }

  void reset() {
    node_positions_.reset();
    rule_positions_.reset();
    quant_positions_.reset();
    info_positions_.reset();
    preorder_.clear();

    nodes_by_name_.clear();
    rules_by_name_.clear();
    quants_by_name_.clear();
    node_info_.clear();
    nodes_collected_ = rules_collected_ = quants_collected_ = info_collected_ = false;
  }
};

class Individual {
protected:
  UnparserRule* root_;

private:
  bool delete_root_;
  Annotations* annot_{};

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

  virtual std::string name() const { return {}; }

  Annotations* annotations() {
    if (!annot_) {
      annot_ = new Annotations(root());
    }
    return annot_;
  }

  // Must be called after the tree of the individual has been changed.
  void reset_annotations() {
    delete annot_;
    annot_ = nullptr;
  }

  // A new individual with a clone of the tree of this individual. The
  // annotations of the clone are not collected again but are derived from
  // the annotations of this individual (whose pointer-free form they share).
  Individual* clone(bool delete_root = true) {
    auto r = root();
    auto copy = new Individual(r ? r->clone() : nullptr, delete_root);
    if (r) {
      copy->annot_ = new Annotations(copy->root(), *annotations());
    }
    return copy;
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
