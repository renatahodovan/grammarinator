// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_RULE_HPP
#define GRAMMARINATOR_RUNTIME_RULE_HPP

#include <algorithm>
#include <format>
#include <limits>
#include <string>
#include <vector>

namespace grammarinator {
namespace runtime {

class RuleSize {
public:
  int depth;
  int tokens;

  constexpr RuleSize() noexcept : RuleSize(0, 0) {}
  constexpr RuleSize(int depth, int tokens) noexcept : depth(depth), tokens(tokens) {}
  RuleSize(const RuleSize& other) = default;
  RuleSize& operator=(const RuleSize& other) = default;
  RuleSize(RuleSize&& other) = default;
  RuleSize& operator=(RuleSize&& other) = default;

  static constexpr RuleSize max() { return RuleSize(std::numeric_limits<int>::max(), std::numeric_limits<int>::max()); }

  constexpr RuleSize operator+(const RuleSize& other) const noexcept {
    return RuleSize(depth + other.depth, tokens + other.tokens);
  }
  constexpr RuleSize& operator+=(const RuleSize& other) noexcept {
    depth += other.depth;
    tokens += other.tokens;
    return *this;
  }
  constexpr RuleSize operator-(const RuleSize& other) const noexcept {
    return RuleSize(depth - other.depth, tokens - other.tokens);
  }
  constexpr RuleSize& operator-=(const RuleSize& other) noexcept {
    depth -= other.depth;
    tokens -= other.tokens;
    return *this;
  }

  constexpr bool operator==(const RuleSize& other) const noexcept {
    return depth == other.depth && tokens == other.tokens;
  }
  constexpr bool operator!=(const RuleSize& other) const noexcept {
    return depth != other.depth || tokens != other.tokens;
  }
  constexpr bool operator<=(const RuleSize& other) const noexcept {
    return depth <= other.depth && tokens <= other.tokens;
  }
  constexpr bool operator<(const RuleSize& other) const noexcept {
    return depth < other.depth && tokens < other.tokens;
  }
  constexpr bool operator>=(const RuleSize& other) const noexcept {
    return depth >= other.depth && tokens >= other.tokens;
  }
  constexpr bool operator>(const RuleSize& other) const noexcept {
    return depth > other.depth && tokens > other.tokens;
  }

  std::string format() const {
    return std::format("RuleSize(depth={}, tokens={})", depth, tokens);
  }
};

} // namespace runtime
} // namespace grammarinator

template<>
struct std::formatter<grammarinator::runtime::RuleSize> {
  template<class ParseContext>
  constexpr auto parse(ParseContext& ctx) {
    return ctx.begin();
  }

  template<class FmtContext>
  auto format(const grammarinator::runtime::RuleSize& size, FmtContext& ctx) const {
    return std::format_to(ctx.out(), "{}", size.format());
  }
};

namespace grammarinator {
namespace runtime {

class ParentRule;

class Rule {
public:
  enum RuleType {
    UnlexerRuleType = 0,
    UnparserRuleType,
    UnparserRuleQuantifierType,
    UnparserRuleQuantifiedType,
    UnparserRuleAlternativeType
  };

  class TokenIterator {
  private:
    std::vector<const Rule*> worklist_{};

    TokenIterator() { }

    explicit TokenIterator(const Rule* node) {
      worklist_.push_back(node);
      next();
    }

  public:
    TokenIterator(const TokenIterator& other) = default;
    TokenIterator& operator=(const TokenIterator& other) = default;
    TokenIterator(TokenIterator&& other) = default;
    TokenIterator& operator=(TokenIterator&& other) = default;
    ~TokenIterator() = default;

    TokenIterator& operator++() {
      worklist_.pop_back();
      next();
      return *this;
    }

    bool operator==(const TokenIterator& other) const noexcept { return worklist_ == other.worklist_; }
    bool operator!=(const TokenIterator& other) const noexcept { return worklist_ != other.worklist_; }
    const std::string& operator*();

  private:
    void next();

    friend class Rule;
  };

  enum RuleFormat { StrFormat, ReprFormat, DbgFormat };

  RuleType type;
  std::string name;
  ParentRule* parent{nullptr};

  explicit Rule(RuleType type, const std::string& name) : type(type), name(name) { }
  Rule(const Rule& other) : type(other.type), name(other.name) { }
  Rule& operator=(const Rule& other) = delete;
  Rule(Rule&& other) = delete;
  Rule& operator=(Rule&& other) = delete;
  virtual ~Rule() = default;

  virtual Rule* clone() const = 0;

  virtual bool equals(const Rule& other) const { return type == other.type && name == other.name; }

  bool equalTokens(const Rule& other) const {
    auto it1 = tokens_begin();
    auto it2 = other.tokens_begin();
    while (it1 != tokens_end() && it2 != other.tokens_end()) {
      if (*it1 != *it2) {
        return false;
      }
      ++it1;
      ++it2;
    }
    return it1 == tokens_end() && it2 == other.tokens_end();
  }

  TokenIterator tokens_begin() const { return TokenIterator(this); }
  TokenIterator tokens_end() const { return TokenIterator(); }

  std::string format(RuleFormat spec = StrFormat) const {
    if (spec == Rule::ReprFormat) {
      return format_repr(0);
    } else if (spec == Rule::DbgFormat) {
      return format_dbg(0);
    } else {
      return format_str();
    }
  }

  const std::string& rule_name() const;
  Rule* left_sibling();
  const Rule* left_sibling() const;
  Rule* right_sibling();
  const Rule* right_sibling() const;
  Rule* root() noexcept;
  const Rule* root() const noexcept;
  Rule* replace(Rule* node);
  void remove();

protected:
  std::string indent(int n, const std::string& prefix) const {
    std::string s;
    for (int i = 0; i < n; ++i) {
      s += prefix;
    }
    return s;
  }

  std::string join(const std::string& delim, const std::vector<std::string>& parts) const {
    std::string result;
    for (const auto& part : parts) {
      if (!result.empty()) {
        result += delim;
      }
      result += part;
    }
    return result;
  }

  virtual std::string format_str() const = 0;
  virtual std::string format_repr(int level) const = 0;
  virtual std::string format_dbg(int level) const = 0;

  friend class ParentRule;
};

class ParentRule : public Rule {
public:
  std::vector<Rule*> children{};

protected:
  explicit ParentRule(RuleType type, const std::string& name, const std::vector<Rule*>& children = {})
      : Rule(type, name) {
    add_children(children);
  }

public:
  ParentRule(const ParentRule& other) : Rule(other) {
    for (const Rule* child : other.children) {
      add_child(child->clone());
    }
  }

  ParentRule& operator=(const ParentRule& other) = delete;
  ParentRule(ParentRule&& other) = delete;
  ParentRule& operator=(ParentRule&& other) = delete;

  ~ParentRule() override {
    for (Rule* child : children) {
      delete child;
    }
  }

  bool equals(const Rule& other) const override {
    if (!Rule::equals(other))
      return false;

    std::vector<Rule*> otherChildren = static_cast<const ParentRule&>(other).children;
    if (children.size() != otherChildren.size())
      return false;

    for (size_t i = 0; i < children.size(); ++i) {
      if (!children[i]->equals(*otherChildren[i]))
        return false;
    }
    return true;
  }

  Rule* last_child() { return !children.empty() ? children.back() : nullptr; }

  const Rule* last_child() const { return !children.empty() ? children.back() : nullptr; }

  void insert_child(int idx, Rule* node) {
    if (!node) {
      return;
    }
    node->remove();
    children.insert(children.begin() + idx, node);
    node->parent = this;
  }

  void add_child(Rule* node) {
    if (node) {
      node->remove();
      children.push_back(node);
      node->parent = this;
    }
  }

  void add_children(const std::vector<Rule*>& nodes) {
    for (Rule* node : nodes)
      add_child(node);
  }

  ParentRule& operator+=(Rule* node) {
    add_child(node);
    return *this;
  }

  ParentRule& operator+=(const std::vector<Rule*>& nodes) {
    add_children(nodes);
    return *this;
  }

protected:
  std::string format_repr_children(int level) const {
    std::string child_reprs;
    for (auto const * const child : children) {
      if (!child_reprs.empty()) {
        child_reprs += ",\n";
      }
      child_reprs += child->format_repr(level + 1);
    }
    child_reprs = std::format("children=[\n{}]", child_reprs);
    return child_reprs;
  }

  std::string format_dbg_children(int level) const {
    std::string child_dbgs;
    for (auto const * const child : children) {
      child_dbgs += "\n";
      child_dbgs += child->format_dbg(level + 1);
    }
    return child_dbgs;
  }

  std::string format_str() const override {
    std::string child_strs;
    for (auto const * const child : children) {
      child_strs += child->format_str();
    }
    return child_strs;
  }
};

class UnparserRule : public ParentRule {
public:
  explicit UnparserRule(const std::string& name, const std::vector<Rule*>& children = {})
      : ParentRule(Rule::UnparserRuleType, name, children) { }

  UnparserRule(const UnparserRule& other) = default;
  UnparserRule& operator=(const UnparserRule& other) = delete;
  UnparserRule(UnparserRule&& other) = delete;
  UnparserRule& operator=(UnparserRule&& other) = delete;
  ~UnparserRule() override = default;

  UnparserRule* clone() const override { return new UnparserRule(*this); }

  Rule* get_child(const std::string& child_name, int index = 0) {
    int count = 0;
    std::vector<Rule*> worklist(children.rbegin(), children.rend());

    while (!worklist.empty()) {
      Rule* child = worklist.back();
      worklist.pop_back();

      if (child->type == Rule::UnparserRuleQuantifierType || child->type == Rule::UnparserRuleQuantifiedType || child->type == Rule::UnparserRuleAlternativeType) {
        const auto& grandchildren = static_cast<ParentRule*>(child)->children;
        worklist.insert(worklist.end(), grandchildren.rbegin(), grandchildren.rend());
      } else if (child->name == child_name) {
        if (count++ == index)
          return child;
      }
    }
    return nullptr;
  }

  const Rule* get_child(const std::string& child_name, int index = 0) const {
    int count = 0;
    std::vector<const Rule*> worklist(children.rbegin(), children.rend());

    while (!worklist.empty()) {
      const Rule* child = worklist.back();
      worklist.pop_back();

      if (child->type == Rule::UnparserRuleQuantifierType || child->type == Rule::UnparserRuleQuantifiedType || child->type == Rule::UnparserRuleAlternativeType) {
        const auto& grandchildren = static_cast<const ParentRule*>(child)->children;
        worklist.insert(worklist.end(), grandchildren.rbegin(), grandchildren.rend());
      } else if (child->name == child_name) {
        if (count++ == index)
          return child;
      }
    }
    return nullptr;
  }

protected:
  std::string format_repr(int level) const override {
    std::vector<std::string> parts { std::format("name=\'{}\'", name) };
    if (!children.empty()) {
      parts.push_back(format_repr_children(level));
    }
    return std::format("{}UnparserRule({})", indent(level, "  "), join(", ", parts));
  }

  std::string format_dbg(int level) const override {
    return std::format("{}{}{}", indent(level, "|  "), name, format_dbg_children(level));
  }
};

class UnparserRuleQuantifier : public ParentRule {
public:
  int idx;
  int start;
  int stop;

  explicit UnparserRuleQuantifier(int idx, int start, int stop, const std::vector<Rule*>& children = {})
    : ParentRule(Rule::UnparserRuleQuantifierType, "", children), idx(idx), start(start), stop(stop) { }

  UnparserRuleQuantifier(const UnparserRuleQuantifier& other)
    : ParentRule(other), idx(other.idx), start(other.start), stop(other.stop) { }

  UnparserRuleQuantifier& operator=(const UnparserRuleQuantifier& other) = delete;
  UnparserRuleQuantifier(UnparserRuleQuantifier&& other) = delete;
  UnparserRuleQuantifier& operator=(UnparserRuleQuantifier&& other) = delete;
  ~UnparserRuleQuantifier() override = default;

  UnparserRuleQuantifier* clone() const override { return new UnparserRuleQuantifier(*this); }

  bool equals(const Rule& other) const override {
    if (!ParentRule::equals(other))
      return false;

    const UnparserRuleQuantifier& otherQuant = static_cast<const UnparserRuleQuantifier&>(other);
    return idx == otherQuant.idx && start == otherQuant.start && stop == otherQuant.stop;
  }

protected:
  std::string format_repr(int level) const override {
    std::vector<std::string> parts {
      std::format("idx={}", idx),
      std::format("start={}", start),
      std::format("stop={}", stop)
    };
    if (!children.empty()) {
      parts.push_back(format_repr_children(level));
    }
    return std::format("{}UnparserRuleQuantifier({})", indent(level, "  "), join(", ", parts));
  }

  std::string format_dbg(int level) const override {
    return std::format("{}UnparserRuleQuantifier:[{}]{}", indent(level, "|  "), idx, format_dbg_children(level));
  }
};

class UnparserRuleQuantified : public ParentRule {
public:
  explicit UnparserRuleQuantified(const std::vector<Rule*>& children = {})
    : ParentRule(Rule::UnparserRuleQuantifiedType, "", children) { }

  UnparserRuleQuantified(const UnparserRuleQuantified& other)
    : ParentRule(other) { }

  UnparserRuleQuantified& operator=(const UnparserRuleQuantified& other) = delete;
  UnparserRuleQuantified(UnparserRuleQuantified&& other) = delete;
  UnparserRuleQuantified& operator=(UnparserRuleQuantified&& other) = delete;
  ~UnparserRuleQuantified() override = default;

  UnparserRuleQuantified* clone() const override { return new UnparserRuleQuantified(*this); }

protected:
  std::string format_repr(int level) const override {
    return std::format("{}UnparserRuleQuantified({})", indent(level, "  "), !children.empty() ? format_repr_children(level) : "");
  }

  std::string format_dbg(int level) const override {
    return std::format("{}UnparserRuleQuantified{}", indent(level, "|  "), format_dbg_children(level));
  }
};

class UnparserRuleAlternative : public ParentRule {
public:
  int alt_idx;
  int idx;

  UnparserRuleAlternative(int alt_idx, int idx, const std::vector<Rule*>& children = {})
    : ParentRule(Rule::UnparserRuleAlternativeType, "", children), alt_idx(alt_idx), idx(idx) { }

  UnparserRuleAlternative(const UnparserRuleAlternative& other)
    : ParentRule(other), alt_idx(other.alt_idx), idx(other.idx) { }

  UnparserRuleAlternative& operator=(const UnparserRuleAlternative& other) = delete;
  UnparserRuleAlternative(UnparserRuleAlternative&& other) = delete;
  UnparserRuleAlternative& operator=(UnparserRuleAlternative&& other) = delete;
  ~UnparserRuleAlternative() override = default;

  UnparserRuleAlternative* clone() const override { return new UnparserRuleAlternative(*this); }

  bool equals(const Rule& other) const override {
    if (!ParentRule::equals(other))
      return false;

    const UnparserRuleAlternative& otherAlt = static_cast<const UnparserRuleAlternative&>(other);
    return alt_idx == otherAlt.alt_idx && idx == otherAlt.idx;
  }

protected:
  std::string format_repr(int level) const override {
    std::vector<std::string> parts {
      std::format("alt_idx={}", alt_idx),
      std::format("idx={}", idx)
    };
    if (!children.empty()) {
      parts.push_back(format_repr_children(level));
    }
    return std::format("{}UnparserRuleAlternative({})", indent(level, "  "), join(", ", parts));
  }

  std::string format_dbg(int level) const override {
    return std::format("{}UnparserRuleAlternative:[{}/{}]{}", indent(level, "|  "), alt_idx, idx, format_dbg_children(level));
  }
};

class UnlexerRule : public Rule {
public:
  std::string src;
  RuleSize size;
  bool immutable;

  explicit UnlexerRule(const std::string& name, bool immutable = false)
      : UnlexerRule(name, "", RuleSize(), immutable) { }

  UnlexerRule(const std::string& name, const std::string& src, const RuleSize& size, bool immutable)
      : Rule(Rule::UnlexerRuleType, name), src(src), size(size), immutable(immutable) { }

  UnlexerRule(const UnlexerRule& other)
      : Rule(other), src(other.src), size(other.size), immutable(other.immutable) { }

  UnlexerRule& operator=(const UnlexerRule& other) = delete;
  UnlexerRule(UnlexerRule&& other) = delete;
  UnlexerRule& operator=(UnlexerRule&& other) = delete;
  ~UnlexerRule() override = default;

  UnlexerRule* clone() const override { return new UnlexerRule(*this); }

  bool equals(const Rule& other) const override {
    if (!Rule::equals(other))
      return false;

    const UnlexerRule& otherRule = static_cast<const UnlexerRule&>(other);
    return src == otherRule.src && immutable == otherRule.immutable;
  }

protected:
  std::string format_str() const override {
    return src;
  }

  std::string format_repr(int level) const override {
    std::vector<std::string> parts;
    if (!name.empty()) {
      parts.push_back(std::format("name=\'{}\'", name));
    }
    if (!src.empty()) {
      parts.push_back(std::format("src=\'{}\'", src));
    }
    if ((!src.empty() && size != RuleSize(1, 1)) || (src.empty() && size != RuleSize(0, 0))) {
      parts.push_back(std::format("size={}", size));
    }
    if (immutable) {
      parts.push_back("immutable=True");
    }
    return std::format("{}UnlexerRule({})", indent(level, "  "), join(", ", parts));
  }

  std::string format_dbg(int level) const override {
    return std::format("{}{}{}\'{}\'{}", indent(level, "|  "), name, !name.empty() ? ":" : "", src, immutable ? " (immutable)" : "");
  }
};

inline const std::string& Rule::TokenIterator::operator*() {
  return static_cast<const UnlexerRule*>(worklist_.back())->src;
}

inline void Rule::TokenIterator::next() {
  while (!worklist_.empty()) {
    const Rule* node = worklist_.back();
    if (node->type == Rule::UnlexerRuleType) {
      if (static_cast<const UnlexerRule*>(node)->src.empty()) {
        worklist_.pop_back();
      } else {
        break;
      }
    } else {
      const ParentRule* parent_node = static_cast<const ParentRule*>(node);
      worklist_.pop_back();
      for (auto it = parent_node->children.rbegin(); it != parent_node->children.rend(); ++it) {
        worklist_.push_back(*it);
      }
    }
  }
}

inline Rule* Rule::left_sibling() {
  if (!parent) {
    return nullptr;
  }
  auto it = std::find(parent->children.begin(), parent->children.end(), this);
  if (it == parent->children.begin()) {
    return nullptr;
  }
  return *(it - 1);
}

inline const Rule* Rule::left_sibling() const {
  if (!parent) {
    return nullptr;
  }
  auto it = std::find(parent->children.cbegin(), parent->children.cend(), this);
  if (it == parent->children.cbegin()) {
    return nullptr;
  }
  return *(it - 1);
}

inline Rule* Rule::right_sibling() {
  if (!parent) {
    return nullptr;
  }
  auto rit = std::find(parent->children.rbegin(), parent->children.rend(), this);
  if (rit == parent->children.rbegin()) {
    return nullptr;
  }
  return *(rit - 1);
}

inline const Rule* Rule::right_sibling() const {
  if (!parent) {
    return nullptr;
  }
  auto rit = std::find(parent->children.crbegin(), parent->children.crend(), this);
  if (rit == parent->children.crbegin()) {
    return nullptr;
  }
  return *(rit - 1);
}

inline Rule* Rule::root() noexcept {
  Rule* node = this;
  while (node->parent) {
    node = node->parent;
  }
  return node;
}

inline const Rule* Rule::root() const noexcept {
  const Rule* node = this;
  while (node->parent) {
    node = node->parent;
  }
  return node;
}

inline const std::string& Rule::rule_name() const {
  static const std::string empty{};
  auto r = this;
  while (r) {
    if (!r->name.empty()) {
      return r->name;
    }
    r = r->parent;
  }
  return empty;
}

inline Rule* Rule::replace(Rule* node) {
  node->remove();
  if (parent && node != this) {
    auto it = std::find(parent->children.begin(), parent->children.end(), this);
    *it = node;
    node->parent = parent;
    parent = nullptr;
  }
  return node;
}

inline void Rule::remove() {
  if (parent) {
    auto it = std::find(parent->children.begin(), parent->children.end(), this);
    parent->children.erase(it);
    parent = nullptr;
  }
}

} // namespace runtime
} // namespace grammarinator

template<>
struct std::formatter<grammarinator::runtime::Rule> {
  template<class ParseContext>
  constexpr auto parse(ParseContext& ctx) {
    auto it = ctx.begin();
    if (it == ctx.end())
      return it;

    if (*it == 's') {
      spec = grammarinator::runtime::Rule::StrFormat;
      ++it;
    } else if (*it == 'r') {
      spec = grammarinator::runtime::Rule::ReprFormat;
      ++it;
    } else if (*it == '|') {
      spec = grammarinator::runtime::Rule::DbgFormat;
      ++it;
    }
    return it;
  }

  template<class FmtContext>
  auto format(const grammarinator::runtime::Rule& node, FmtContext& ctx) const {
    return std::format_to(ctx.out(), "{}", node.format(spec));
  }

  grammarinator::runtime::Rule::RuleFormat spec{grammarinator::runtime::Rule::StrFormat};
};

#endif // GRAMMARINATOR_RUNTIME_RULE_HPP
