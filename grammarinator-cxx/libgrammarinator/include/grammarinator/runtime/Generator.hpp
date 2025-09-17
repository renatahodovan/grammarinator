// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_GENERATOR_HPP
#define GRAMMARINATOR_RUNTIME_GENERATOR_HPP

#include "../util/print.hpp"
#include "DefaultModel.hpp"
#include "Listener.hpp"
#include "Model.hpp"
#include "Rule.hpp"

#include <string>
#include <utility>
#include <vector>

namespace grammarinator {
namespace runtime {

class Generator {
public:
  Model* _model;
  RuleSize _size{};
  RuleSize _limit;

protected:
  std::vector<Listener*> _listeners;

public:
  explicit Generator(Model* model = new DefaultModel(), const std::vector<Listener*>& listeners = {}, const RuleSize& limit = RuleSize::max())
      : _model(model), _limit(limit), _listeners(listeners) {
    _model->gen = this;  // NOTE: Python version does not set model's gen field
  }

  Generator(const Generator& other) = delete;
  Generator& operator=(const Generator& other) = delete;
  Generator(Generator&& other) = delete;
  Generator& operator=(Generator&& other) = delete;

  virtual ~Generator() {
    delete _model;
    for (Listener* listener : _listeners) {
      delete listener;
    }
  }

  template<class G, class F, class... Fargs>
  void _reserve(int reserve, G g, F fn, Fargs... args) {
    _size.tokens += reserve;
    (g->*fn)(args...);
    _size.tokens -= reserve;
  }

  void _enter_rule(Rule* node) const {
    for (Listener* listener : _listeners) {
      listener->enter_rule(node);
    }
  }

  void _exit_rule(Rule* node) const {
    for (int i = _listeners.size() - 1; i >= 0; i--) {
      _listeners[i]->exit_rule(node);
    }
  }

protected:
  static std::vector<std::string> _charset(const std::vector<std::pair<int, int>>& ranges) {
    std::vector<std::string> charset;
    for (const auto& range : ranges) {
      for (int codepoint = range.first; codepoint < range.second; ++codepoint) {
        char utf8[4];
        int size = 0;
        if (codepoint < 0x80) {
          // U+0000 .. U+007F: 0xxxxxxx
          utf8[0] = (char)codepoint;
          size = 1;
        } else if (codepoint < 0x800) {
          // U+0080 .. U+07FF: 110xxxxx, 10xxxxxx
          utf8[0] = (char)(((codepoint >> 6) & 0b00011111 )| 0b11000000);
          utf8[1] = (char)((codepoint & 0b00111111) | 0b10000000);
          size = 2;
        } else if (codepoint < 0x10000) {
          // U+0800 .. U+FFFF: 1110xxxx, 10xxxxxx, 10xxxxxx
          utf8[0] = (char)(((codepoint >> 12) & 0b00001111) | 0b11100000);
          utf8[1] = (char)(((codepoint >> 6) & 0b00111111) | 0b10000000);
          utf8[2] = (char)((codepoint & 0b00111111) | 0b10000000);
          size = 3;
        } else if (codepoint < 0x110000) {
          // U+10000 .. U+10FFFF: 11110xxx, 10xxxxxx, 10xxxxxx, 10xxxxxx
          utf8[0] = (char)(((codepoint >> 18) & 0b00000111) | 0b11110000);
          utf8[1] = (char)(((codepoint >> 12) & 0b00111111) | 0b10000000);
          utf8[2] = (char)(((codepoint >> 6) & 0b00111111) | 0b10000000);
          utf8[3] = (char)((codepoint & 0b00111111) | 0b10000000);
          size = 4;
        }
        charset.push_back(std::string(utf8, size));
      }
    }
    return charset;
  }
};

class Context {
public:
  Rule* node;

protected:
  explicit Context(Rule* node) : node(node) { }
};

class RuleContext : public Context {
public:
  Generator* gen;
  Context* ctx;

protected:
  RuleContext(Generator* gen, Rule* node) : Context(node), gen(gen) {
    ctx = this;
  }

  void enter() {
    gen->_size.depth++;
    gen->_enter_rule(node);
  }

  void exit() {
    gen->_exit_rule(node);
    gen->_size.depth--;
  }

public:
  Rule* current() {
    return ctx->node;
  }
};

class UnlexerRuleContext : public RuleContext {
private:
  bool parent_is_unlexer_rule;
  int start_depth;
  std::string parent_name;

public:
  UnlexerRuleContext(Generator* gen, const std::string& name, Rule* parent = nullptr, bool immutable = false)
      : RuleContext(gen, parent && parent->type == Rule::UnlexerRuleType ? parent : new UnlexerRule(name, immutable)),
        parent_is_unlexer_rule(parent && parent->type == Rule::UnlexerRuleType),
        start_depth(0), parent_name() {
    if (parent_is_unlexer_rule) {
      // If parent node is also an UnlexerRule then this is a sub-rule and
      // actually no child node is created, but the parent is kept as the
      // current node
      // So, save the name of the parent node
      // and rename it to reflect the name of the sub-rule
      parent_name = parent->name;
      parent->name = name;
    } else {
      if (parent) {
        static_cast<ParentRule*>(parent)->add_child(node);
      }
      start_depth = gen->_size.depth;
    }

    enter();

    gen->_size.tokens++;
    UnlexerRule* unlexer_node = static_cast<UnlexerRule*>(node);
    unlexer_node->size.tokens++;
    if (gen->_size.depth > unlexer_node->size.depth) {
      unlexer_node->size.depth = gen->_size.depth;
    }
  }

  ~UnlexerRuleContext() {
    exit();

    if (start_depth > 0) {
      static_cast<UnlexerRule*>(node)->size.depth -= start_depth;
    }

    // When exiting a sub-rule, change the name of the current node back to
    // that of the parent
    if (parent_is_unlexer_rule)
      node->name = parent_name;
  }
};

class UnparserRuleContext : public RuleContext {
public:
  UnparserRuleContext(Generator* gen, const std::string& name, Rule* parent = nullptr)
      : RuleContext(gen, new UnparserRule(name)) {
    if (parent) {
      static_cast<ParentRule*>(parent)->add_child(node);
    }
    enter();
  }

  ~UnparserRuleContext() {
    exit();
  }
};

class SubRuleContext : public Context {
protected:
  RuleContext& rule;
  Context* prev_ctx;

  explicit SubRuleContext(RuleContext& rule, Rule* node = nullptr)
      : Context(node ? node : rule.current()), rule(rule), prev_ctx(rule.ctx) {
    if (node) {
      static_cast<ParentRule*>(prev_ctx->node)->add_child(node);
    }
    rule.ctx = this;
  }

  ~SubRuleContext() {
    rule.ctx = prev_ctx;
  }
};

class AlternationContext : public SubRuleContext {
private:
  int idx;
  std::vector<RuleSize> min_sizes;
  int reserve;
  std::vector<double> conditions;
  int orig_depth_limit;
  std::vector<double> weights{};
  int choice{};

public:
  AlternationContext(RuleContext& rule, int idx, const std::vector<RuleSize>& min_sizes, int reserve,
                     const std::vector<double>& conditions)
      : SubRuleContext(rule),
        idx(idx), min_sizes(min_sizes), reserve(reserve), conditions(conditions), orig_depth_limit(rule.gen->_limit.depth) {
    Generator* gen = rule.gen;
    gen->_size.tokens += reserve;

    double wsum = 0.0;
    weights.reserve(conditions.size());
    for (size_t i = 0; i < conditions.size(); ++i) {
      double w = gen->_size + min_sizes[i] <= gen->_limit ? conditions[i] : 0.0;
      weights.push_back(w);
      wsum += w;
    }
    if (wsum == 0.0) {
        RuleSize min_size = RuleSize::max();
        for (size_t i = 0; i < conditions.size(); ++i) {
          if ((conditions[i] > 0.0)
              && ((min_sizes[i].depth < min_size.depth)
                  || (min_sizes[i].depth == min_size.depth && min_sizes[i].tokens < min_size.tokens))) {
            min_size = min_sizes[i];
          }
        }

        RuleSize new_limit = gen->_size + min_size;
        if (new_limit.depth > gen->_limit.depth) {
          grammarinator::util::perrf("max_depth must be temporarily updated from {} to {}", gen->_limit.depth, new_limit.depth);
          gen->_limit.depth = new_limit.depth;
        }
        if (new_limit.tokens > gen->_limit.tokens) {
          grammarinator::util::perrf("max_tokens must be updated from {} to {}", gen->_limit.tokens, new_limit.tokens);
          gen->_limit.tokens = new_limit.tokens;
        }

        weights.clear();
        for (size_t i = 0; i < conditions.size(); ++i) {
          weights.push_back(gen->_size + min_sizes[i] <= gen->_limit ? conditions[i] : 0.0);
        }
    }

    choice = rule.gen->_model->choice(rule.node, idx, weights);
    if (rule.node->type != Rule::UnlexerRuleType) {
      node = new UnparserRuleAlternative(idx, choice);
      static_cast<ParentRule*>(prev_ctx->node)->add_child(node);
    }
  }

  ~AlternationContext() {
    Generator* gen = rule.gen;
    gen->_limit.depth = orig_depth_limit;
    gen->_size.tokens -= reserve;
  }

  int operator()() { return choice; }
};

class QuantifierContext : public SubRuleContext {
private:
  int idx;
  int start;
  int stop;
  RuleSize min_size;
  int reserve;
  int cnt{0};

public:
  QuantifierContext(RuleContext& rule, int idx, int start, int stop, const RuleSize& min_size, int reserve)
      : SubRuleContext(rule, rule.node->type != Rule::UnlexerRuleType ? new UnparserRuleQuantifier(idx, start, stop) : nullptr),
        idx(idx), start(start), stop(stop), min_size(min_size), reserve(reserve) {
    rule.gen->_size.tokens += reserve;
  }

  ~QuantifierContext() {
    rule.gen->_size.tokens -= reserve;
  }

  bool operator()() {
    if (cnt < start) {
      cnt++;
      return true;
    }

    if (cnt < stop
        && rule.gen->_size + min_size <= rule.gen->_limit
        && rule.gen->_model->quantify(rule.node, idx, cnt, start, stop)) {
      cnt++;
      return true;
    }
    return false;
  }
};

class QuantifiedContext : public SubRuleContext {
public:
  explicit QuantifiedContext(RuleContext& rule) : SubRuleContext(rule, rule.node->type != Rule::UnlexerRuleType ? new UnparserRuleQuantified() : nullptr) { }
};

} // namespace runtime
} // namespace grammarinator

#endif // GRAMMARINATOR_RUNTIME_GENERATOR_HPP
