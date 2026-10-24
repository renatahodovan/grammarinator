// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_TOOL_HPP
#define GRAMMARINATOR_TOOL_TOOL_HPP

#include "../runtime/Model.hpp"
#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../util/log.hpp"
#include "../util/print.hpp"
#include "../util/random.hpp"

#include <xxhash.h>

#include <algorithm>
#include <cassert>
#include <deque>
#include <format>
#include <functional>
#include <list>
#include <map>
#include <numeric>
#include <set>
#include <string>
#include <tuple>
#include <unordered_set>
#include <vector>

namespace grammarinator {
namespace tool {

// Decision model wrapper that, in the root rule of the generation, forces
// the given alternatives of some alternations (if they are possible) and
// avoids an alternative of another alternation (if any other alternative is
// possible there).
class SwitchAlternativeModel : public runtime::Model {
private:
  runtime::Model* model;
  std::string rule;
  std::map<int, int> forced_choices;
  int avoided_alt_idx;
  int avoided_choice;

public:
  SwitchAlternativeModel(runtime::Model* model, const std::string& rule, const std::map<int, int>& forced_choices, int avoided_alt_idx, int avoided_choice)
      : Model(), model(model), rule(rule), forced_choices(forced_choices), avoided_alt_idx(avoided_alt_idx), avoided_choice(avoided_choice) { }
  SwitchAlternativeModel(const SwitchAlternativeModel& other) = delete;
  SwitchAlternativeModel& operator=(const SwitchAlternativeModel& other) = delete;
  SwitchAlternativeModel(SwitchAlternativeModel&& other) = delete;
  SwitchAlternativeModel& operator=(SwitchAlternativeModel&& other) = delete;
  ~SwitchAlternativeModel() override { delete model; }

  // Apply the forced and avoided choices in the root rule, otherwise defer to
  // the underlying model.
  int choice(const runtime::Rule* node, int idx, const std::vector<double>& weights) override {
    if (!node->parent && node->name == rule) {
      auto forced_it = forced_choices.find(idx);
      if (forced_it != forced_choices.end() && static_cast<size_t>(forced_it->second) < weights.size() && weights[forced_it->second] > 0.0) {
        return forced_it->second;
      }
      if (idx == avoided_alt_idx && static_cast<size_t>(avoided_choice) < weights.size()) {
        std::vector<double> avoiding_weights(weights);
        avoiding_weights[avoided_choice] = 0.0;
        if (std::accumulate(avoiding_weights.begin(), avoiding_weights.end(), 0.0) > 0.0) {
          return model->choice(node, idx, avoiding_weights);
        }
      }
    }
    return model->choice(node, idx, weights);
  }

  // Defer to the underlying model.
  bool quantify(const runtime::Rule* node, int idx, int cnt, int start, int stop, double prob = 0.5) override {
    return model->quantify(node, idx, cnt, start, stop, prob);
  }

  // Defer to the underlying model.
  std::string charset(const runtime::Rule* node, int idx, const std::vector<std::string>& chars) override {
    return model->charset(node, idx, chars);
  }
};

template<class GeneratorFactoryClass>
class Tool {
public:
  using SerializerFn = std::string (*)(const runtime::Rule*);
  using TransformerFn = runtime::Rule* (*)(runtime::Rule*);
  using CreatorFn = std::function<runtime::Rule*(runtime::Individual*, runtime::Individual*)>;

  GeneratorFactoryClass generator_factory;
  std::string rule;
  runtime::RuleSize limit;
  std::vector<TransformerFn> transformers;
  SerializerFn serializer;
  std::string last_mutator;
  std::string last_individual;

protected:
  std::map<std::string, CreatorFn> generators;
  std::map<std::string, CreatorFn> mutators;
  std::map<std::string, CreatorFn> recombiners;
  std::unordered_set<std::string> allowlist;
  std::unordered_set<std::string> blocklist;

  runtime::Population* population;
  int memo_size;
  std::set<XXH64_hash_t> memo;
  std::list<std::set<XXH64_hash_t>::iterator> memo_order;

  void allow_creator(std::map<std::string, CreatorFn>& creator_map, const std::string& name, CreatorFn creator) {
    if (!blocklist.contains(name) && (allowlist.empty() || allowlist.contains(name))) {
      creator_map.emplace(name, creator);
    }
  }

public:
  explicit Tool(const GeneratorFactoryClass& generator_factory, const std::string& rule = "",
                const runtime::RuleSize& limit = runtime::RuleSize::max(), runtime::Population* population = nullptr,
                bool generate = true, bool mutate = true, bool recombine = true, bool unrestricted = true,
                const std::unordered_set<std::string> allowlist = {}, const std::unordered_set<std::string> blocklist = {},
                const std::vector<TransformerFn>& transformers = {}, SerializerFn serializer = nullptr,
                int memo_size = 0)
      : generator_factory(generator_factory), rule(rule), limit(limit), population(population),
        transformers(transformers), serializer(serializer), memo_size(memo_size),
        allowlist(allowlist), blocklist(blocklist) {
    if (generate) {
      allow_creator(generators, "generate", [this](auto i1, auto i2) { return this->generate(); });
    }
    if (mutate) {
      allow_creator(mutators, "regenerate_rule", [this](auto i1, auto i2) { return regenerate_rule(i1); });
      allow_creator(mutators, "switch_alternative_keep_children", [this](auto i1, auto i2) { return switch_alternative_keep_children(i1); });
      allow_creator(mutators, "delete_quantified", [this](auto i1, auto i2) { return delete_quantified(i1); });
      allow_creator(mutators, "replicate_quantified", [this](auto i1, auto i2) { return replicate_quantified(i1); });
      allow_creator(mutators, "replicate_with_variation", [this](auto i1, auto i2) { return replicate_with_variation(i1); });
      allow_creator(mutators, "shuffle_quantifieds", [this](auto i1, auto i2) { return shuffle_quantifieds(i1); });
      allow_creator(mutators, "hoist_rule", [this](auto i1, auto i2) { return hoist_rule(i1); });
      allow_creator(mutators, "pump_recursion", [this](auto i1, auto i2) { return pump_recursion(i1); });
      allow_creator(mutators, "swap_local_nodes", [this](auto i1, auto i2) { return swap_local_nodes(i1); });
      allow_creator(mutators, "copy_local_node", [this](auto i1, auto i2) { return copy_local_node(i1); });
      allow_creator(mutators, "insert_local_node", [this](auto i1, auto i2) { return insert_local_node(i1); });
      allow_creator(mutators, "merge_names", [this](auto i1, auto i2) { return merge_names(i1); });
      if (unrestricted) {
        allow_creator(mutators, "unrestricted_delete", [this](auto i1, auto i2) { return unrestricted_delete(i1); });
        allow_creator(mutators, "unrestricted_hoist_rule", [this](auto i1, auto i2) { return unrestricted_hoist_rule(i1); });
      }
    }
    if (recombine) {
      allow_creator(recombiners, "replace_node", [this](auto i1, auto i2) { return replace_node(i1, i2); });
      allow_creator(recombiners, "insert_quantified", [this](auto i1, auto i2) { return insert_quantified(i1, i2); });
      // if (unrestricted) {
      //   allow_creator(recombiners, "replace_node_random", [this](auto i1, auto i2) { return replace_node_random(i1, i2); });  // FIXME: unused?
      // }
    }
  }

  Tool(const Tool& other) = delete;
  Tool& operator=(const Tool& other) = delete;
  Tool(Tool&& other) = delete;
  Tool& operator=(Tool&& other) = delete;
  virtual ~Tool() = default;

protected:
  runtime::Individual* ensure_individual(runtime::Individual* individual) const {
    if (individual == nullptr) {
      assert(population != nullptr);
      individual = population->select_individual();
    }
    return individual;
  }

  std::pair<runtime::Individual*, runtime::Individual*> ensure_individuals(runtime::Individual* individual1, runtime::Individual* individual2) const {
    individual1 = ensure_individual(individual1);
    if (individual2 == nullptr) {
      assert(population != nullptr);
      individual2 = population->select_individual(individual1);
    }
    return {individual1, individual2};
  }

  virtual std::map<std::string, CreatorFn>::iterator select_creator(std::map<std::string, CreatorFn>& creators, runtime::Individual* individual1, runtime::Individual* individual2) const {
    size_t idx = util::random_int<size_t>(0, creators.size() - 1);
    return std::next(creators.begin(), idx);
  }

  runtime::Rule* create_tree(std::map<std::string, CreatorFn>& creators, runtime::Individual* individual1, runtime::Individual* individual2) {
    // Note: creators is potentially modified (creators that return null are removed). Always ensure it is a copy when calling this method.
    runtime::Rule* root = nullptr;

    while (!creators.empty()) {
      auto creatorit = select_creator(creators, individual1, individual2);
      if (!generators.contains(creatorit->first)) {
        // Individuals may be loaded lazily, so check them only when the selected creator needs them,
        // and drop all creators that depend on an individual that could not be loaded.
        if (!individual1->root()) {
          std::erase_if(creators, [this](const auto& creator) { return !generators.contains(creator.first); });
          continue;
        }
        if (recombiners.contains(creatorit->first) && !individual2->root()) {
          std::erase_if(creators, [this](const auto& creator) { return recombiners.contains(creator.first); });
          continue;
        }
        GRAMMARINATOR_LOG_TRACE("Original test: '{}'", serializer(individual1->root()));
      }
      last_mutator = creatorit->first;
      root = creatorit->second(individual1, individual2);
      if (root) {
        last_individual = individual1 && !generators.contains(creatorit->first) ? individual1->name() : "";
        break;
      }
      creators.erase(creatorit->first);
    }
    if (!root) {
      GRAMMARINATOR_LOG_WARN("No test creator could produce a tree.");
      return nullptr;
    }
    for (const auto& transformer : transformers) {
      root = transformer(root);
    }
    return root;
  }

public:
  bool memoize_test(const void *input, size_t length) {
    // Memoize the (hash of the) test case. The size of the memo is capped by
    // ``memo_size``, i.e., it contains at most that many test cases.
    // Returns ``false`` if the test case was already in the memo, ``true``
    // if it got added now (or memoization is disabled by ``memo_size=0``).
    // When the memo is full and a new test case is added, the oldest entry
    // is evicted.
    if (memo_size < 1) {
      return true;
    }

    auto test = XXH3_64bits(input, length);
    auto inserted = memo.insert(test);  // {iterator, success}
    if (!inserted.second) {
      return false;
    }
    memo_order.push_back(inserted.first);

    if (memo.size() > memo_size) {
      memo.erase(memo_order.front());
      memo_order.pop_front();
    }

    return true;
  }

  runtime::Rule* mutate(runtime::Individual* individual = nullptr) {
    // Regenerate root if it has no children.
    individual = ensure_individual(individual);
    auto real_root = static_cast<runtime::ParentRule*>(individual->root());
    if (!real_root) {
      return nullptr;
    }

    if (real_root->children.empty()) {
      GRAMMARINATOR_LOG_DEBUG("Mutate empty tree. Regenerate {}", real_root->name);
      auto new_root = generate(real_root->name);
      for (const auto& transformer : transformers) {
        new_root = transformer(new_root);
      }
      real_root->replace(new_root);
      delete real_root;
      return individual->root();
    }

    auto creators = mutators;
    return create_tree(creators, individual, nullptr);
  }

  runtime::Rule* recombine(runtime::Individual* recipient_individual = nullptr, runtime::Individual* donor_individual = nullptr) {
    auto [ensured_recipient, ensured_donor] = ensure_individuals(recipient_individual, donor_individual);
    auto creators = recombiners;
    return create_tree(creators, ensured_recipient, ensured_donor);
  }

  template<typename... Args>
  void print_mutator(std::string_view fmt, Args&&... args) {
    GRAMMARINATOR_LOG_DEBUG("GrammarinatorMutator [{}]", std::vformat(fmt, std::make_format_args(args...)));
  }

  runtime::Rule* generate(const std::string& rule_name = "", const runtime::RuleSize& reserve = runtime::RuleSize(),
                          const std::function<runtime::Model*(runtime::Model*)>& wrap_model = nullptr) {
    auto generator = generator_factory(limit - reserve);
    if (wrap_model) {
      generator._model = wrap_model(generator._model);
      generator._model->gen = &generator;
    }
    std::string rn = !rule_name.empty() ? rule_name : !rule.empty() ? rule : generator_factory._default_rule;
    auto rule_it = generator._rule_fns.find(rn);
    if (rule_it == generator._rule_fns.end()) {
      GRAMMARINATOR_LOG_ERROR("Rule {} not found.", rn);
      return nullptr;
    }
    print_mutator("{}: {}", __func__, rn);
    return (generator.*rule_it->second)(nullptr);
  }

  runtime::Rule* regenerate_rule(runtime::Individual* individual = nullptr,
                                 const std::function<runtime::Model*(runtime::Model*)>& wrap_model = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();
    const auto& node_info = annot->node_info();

    int root_tokens = node_info.at(root).tokens;
    std::vector<runtime::Rule*> options;
    for (const auto& [node_id, nodes] : annot->rules_by_name()) {
      // TODO: this should be removed or transformed to an assert.
      if (generator_factory._rule_sizes.find(node_id.name) == generator_factory._rule_sizes.end()) {
        GRAMMARINATOR_LOG_ERROR("Unknown rule name in generation: {}.", node_id.name);
        continue;
      }
      auto rule_size = generator_factory._rule_sizes.at(node_id.name);
      for (auto node : nodes) {
        if (node_info.at(node).level + rule_size.depth < limit.depth
            // Heuristic: regenerate rules with fewer tokens than the half of the whole tree
            // && root_tokens / 2 > node_info.at(node).tokens
            && root_tokens - node_info.at(node).tokens + rule_size.tokens < limit.tokens)
          options.push_back(node);
      }
    }

    if (!options.empty()) {
      auto mutated_node = options[util::random_int<size_t>(0, options.size() - 1)];
      print_mutator("{}: {}", __func__, mutated_node->name);
      runtime::RuleSize reserve(node_info.at(mutated_node).level,
                                root_tokens - node_info.at(mutated_node).tokens);
      auto new_node = mutated_node->replace(generate(mutated_node->name, reserve, wrap_model));
      delete mutated_node;
      return individual->root();
    }

    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Regenerate a rule node so that a different alternative is chosen at one
  // of its alternations, and put the old rule children of the node in place of
  // the newly generated ones of the same rule (e.g., a + b -> a * b).
  runtime::Rule* switch_alternative_keep_children(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();
    const auto& node_info = annot->node_info();

    // Only alternatives are considered that are below their rule node only
    // via other alternatives (and not via quantifiers). So, if the choices
    // of these ancestor alternatives are kept when the rule is regenerated,
    // the alternation of the selected alternative is reached exactly once.
    int root_tokens = node_info.at(root).tokens;
    std::vector<runtime::UnparserRuleAlternative*> options;
    for (const auto& [key, nodes] : annot->nodes_by_name()) {
      if (key.type != runtime::Annotations::NodeKey::AlternativeKey) {
        continue;
      }
      for (auto node : nodes) {
        auto rule_node = node->parent;
        while (rule_node->type == runtime::Rule::UnparserRuleAlternativeType) {
          rule_node = rule_node->parent;
        }
        if (rule_node == root || rule_node->type != runtime::Rule::UnparserRuleType) {
          continue;
        }
        auto rule_size_it = generator_factory._rule_sizes.find(rule_node->name);
        if (rule_size_it != generator_factory._rule_sizes.end()
            && node_info.at(rule_node).level + rule_size_it->second.depth < limit.depth
            && root_tokens - node_info.at(rule_node).tokens + rule_size_it->second.tokens < limit.tokens) {
          options.push_back(static_cast<runtime::UnparserRuleAlternative*>(node));
        }
      }
    }

    // Rule nodes below a rule node that are not below another rule node.
    auto rule_children = [](const auto& self, runtime::Rule* node, std::vector<runtime::Rule*>& children) -> void {
      for (auto child : static_cast<runtime::ParentRule*>(node)->children) {
        if (child->type == runtime::Rule::UnparserRuleType || child->type == runtime::Rule::UnlexerRuleType) {
          if (child->type != runtime::Rule::UnlexerRuleType || !static_cast<runtime::UnlexerRule*>(child)->immutable) {
            children.push_back(child);
          }
        } else {
          self(self, child, children);
        }
      }
    };

    // The alternative node of the given alternation below a rule node, if it is not below another rule node.
    auto find_alternative = [](const auto& self, runtime::Rule* node, int alt_idx) -> runtime::UnparserRuleAlternative* {
      for (auto child : static_cast<runtime::ParentRule*>(node)->children) {
        if (child->type == runtime::Rule::UnparserRuleAlternativeType && static_cast<runtime::UnparserRuleAlternative*>(child)->alt_idx == alt_idx) {
          return static_cast<runtime::UnparserRuleAlternative*>(child);
        }
        if (child->type != runtime::Rule::UnparserRuleType && child->type != runtime::Rule::UnlexerRuleType) {
          if (auto found = self(self, child, alt_idx)) {
            return found;
          }
        }
      }
      return nullptr;
    };

    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto alt_node : options) {
      std::map<int, int> forced_choices;
      auto rule_node = alt_node->parent;
      while (rule_node->type == runtime::Rule::UnparserRuleAlternativeType) {
        forced_choices[static_cast<runtime::UnparserRuleAlternative*>(rule_node)->alt_idx] = static_cast<runtime::UnparserRuleAlternative*>(rule_node)->idx;
        rule_node = rule_node->parent;
      }
      runtime::RuleSize reserve(node_info.at(rule_node).level, root_tokens - node_info.at(rule_node).tokens);
      auto new_rule_node = generate(rule_node->name, reserve, [rule_node, &forced_choices, alt_node](runtime::Model* model) {
        return new SwitchAlternativeModel(model, rule_node->name, forced_choices, alt_node->alt_idx, alt_node->idx);
      });

      auto new_alt_node = find_alternative(find_alternative, new_rule_node, alt_node->alt_idx);
      if (!new_alt_node || new_alt_node->idx == alt_node->idx) {
        delete new_rule_node;
        continue;
      }

      // Put the old rule children in place of the new ones of the same rule,
      // in order, as long as the token limit allows.
      std::vector<runtime::Rule*> old_children;
      rule_children(rule_children, rule_node, old_children);
      std::map<std::string, std::deque<runtime::Rule*>> old_children_by_name;
      for (auto old_child : old_children) {
        old_children_by_name[old_child->name].push_back(old_child);
      }

      runtime::Annotations new_annot(new_rule_node);
      const auto& new_node_info = new_annot.node_info();
      int tokens = root_tokens - node_info.at(rule_node).tokens + new_node_info.at(new_rule_node).tokens;
      std::vector<runtime::Rule*> new_children;
      rule_children(rule_children, new_rule_node, new_children);
      for (auto new_child : new_children) {
        auto& candidates = old_children_by_name[new_child->name];
        if (candidates.empty()) {
          continue;
        }
        auto old_child = candidates.front();
        int new_tokens = tokens - new_node_info.at(new_child).tokens + node_info.at(old_child).tokens;
        if (new_tokens > limit.tokens) {
          continue;
        }
        candidates.pop_front();
        new_child->replace(old_child);
        delete new_child;
        tokens = new_tokens;
      }

      print_mutator("{}: {}, {}, {}", __func__, rule_node->name, alt_node->alt_idx, alt_node->idx);
      rule_node->replace(new_rule_node);
      delete rule_node;
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* replace_node(runtime::Individual* recipient_individual = nullptr, runtime::Individual* donor_individual = nullptr) {
    auto [ensured_recipient, ensured_donor] = ensure_individuals(recipient_individual, donor_individual);
    auto recipient_root = ensured_recipient->root();
    auto recipient_annot = ensured_recipient->annotations();
    const auto& recipient_node_info = recipient_annot->node_info();
    auto donor_annot = ensured_donor->annotations();
    const auto& donor_node_info = donor_annot->node_info();

    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> recipient_lookup = recipient_annot->nodes_by_name();
    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> donor_lookup = donor_annot->nodes_by_name();

    std::vector<runtime::Annotations::NodeKey> common_types;
    for (const auto& [recipient_key, value] : recipient_lookup) {
      if (donor_lookup.find(recipient_key) != donor_lookup.end()) {
        common_types.push_back(recipient_key);
      }
    }
    // std::sort(common_types.begin(), common_types.end());

    std::vector<std::tuple<runtime::Annotations::NodeKey, runtime::Rule*>> recipient_options;
    for (const auto& rule_name : common_types) {
      for (auto recipient_node : recipient_lookup[rule_name]) {
        if (recipient_node->parent) {
          recipient_options.emplace_back(rule_name, recipient_node);
        }
      }
    }

    int recipient_root_tokens = recipient_node_info.at(recipient_root).tokens;
    std::shuffle(recipient_options.begin(), recipient_options.end(), util::random_engine);
    for (auto& [rule_name, recipient_node] : recipient_options) {
      auto& donor_options = donor_lookup[rule_name];
      int recipient_node_level = recipient_node_info.at(recipient_node).level;
      int recipient_node_tokens = recipient_node_info.at(recipient_node).tokens;
      std::shuffle(donor_options.begin(), donor_options.end(), util::random_engine);
      for (auto donor_node : donor_options) {
        // Make sure that the output tree won't exceed the depth limit.
        if (recipient_node_level + donor_node_info.at(donor_node).depth <= limit.depth
            && recipient_root_tokens - recipient_node_tokens + donor_node_info.at(donor_node).tokens < limit.tokens) {
          // Cloning is needed since donor_root will be deleted by the caller.
          print_mutator("{}: {}", __func__, recipient_node->rule_name());
          recipient_node->replace(donor_node->clone());
          // TODO: this was originally deleted, but caused SEGV.
          delete recipient_node;
          return recipient_root;
        }
      }
    }

    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* insert_quantified(runtime::Individual* recipient_individual = nullptr, runtime::Individual* donor_individual = nullptr) {
    auto [ensured_recipient, ensured_donor] = ensure_individuals(recipient_individual, donor_individual);
    auto recipient_root = ensured_recipient->root();
    auto recipient_annot = ensured_recipient->annotations();
    const auto& recipient_node_info = recipient_annot->node_info();
    auto& recipient_quants_by_name = recipient_annot->quants_by_name();
    auto donor_annot = ensured_donor->annotations();
    const auto& donor_node_info = donor_annot->node_info();
    auto& donor_quants_by_name = donor_annot->quants_by_name();

    std::vector<runtime::Annotations::NodeKey> common_types;
    for (const auto& [recipient_key, recipient_quants] : recipient_quants_by_name) {
      if (donor_quants_by_name.find(recipient_key) != donor_quants_by_name.end()) {
        common_types.push_back(recipient_key);
      }
    }
    //std::sort(common_types.begin(), common_types.end());

    std::vector<std::tuple<runtime::Annotations::NodeKey, runtime::UnparserRuleQuantifier*>> recipient_options;
    for (const auto& name : common_types) {
      for (auto node : recipient_quants_by_name[name]) {
        auto quant_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        if (quant_node->children.size() < quant_node->stop) {
          recipient_options.emplace_back(name, quant_node);
        }
      }
    }
    int recipient_root_tokens = recipient_node_info.at(recipient_root).tokens;
    std::shuffle(recipient_options.begin(), recipient_options.end(), util::random_engine);
    for (auto& [rule_name, recipient_node] : recipient_options) {
      int recipient_node_level = recipient_node_info.at(recipient_node).level;
      std::vector<runtime::Rule*> donor_options;
      for (auto quantifier : donor_quants_by_name[rule_name]) {
        for (auto node : static_cast<runtime::UnparserRuleQuantifier*>(quantifier)->children) {
          donor_options.push_back(node);
        }
      }
      std::shuffle(donor_options.begin(), donor_options.end(), util::random_engine);
      for (auto donor_node : donor_options) {
        // Make sure that the output tree won't exceed the depth limit.
        if (recipient_node_level + donor_node_info.at(donor_node).depth <= limit.depth
            && recipient_root_tokens + donor_node_info.at(donor_node).tokens < limit.tokens) {
          recipient_node->insert_child(recipient_node->children.size() > 0 ? util::random_int<size_t>(0, recipient_node->children.size() - 1) : 0,
                                       donor_node->clone());
          print_mutator("{}: {}, {}", __func__, recipient_node->rule_name(), recipient_node->idx);
          return recipient_root;
        }
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* delete_quantified(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::Rule*> options;
    for (const auto& [quant_id, quant_nodes] : annot->quants_by_name()) {
      for (auto node : quant_nodes) {
        auto quant_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        if (quant_node->children.size() > quant_node->start) {
          for (auto child : quant_node->children) {
            options.push_back(child);
          }
        }
      }
    }

    if (!options.empty()) {
      auto removed_node = options[util::random_int<size_t>(0, options.size() - 1)];
      print_mutator("{}: {}, {}", __func__, removed_node->rule_name(), static_cast<runtime::UnparserRuleQuantifier*>(removed_node->parent)->idx);
      removed_node->remove();
      delete removed_node;
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* unrestricted_delete(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::Rule*> options = annot->rules();

    if (!options.empty()) {
      auto removed_node = options[util::random_int<size_t>(0, options.size() - 1)];
      print_mutator("{}: {}", __func__, removed_node->name);
      removed_node->remove();
      delete removed_node;
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* replicate_quantified(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();
    const auto& node_info = annot->node_info();

    int root_tokens = node_info.at(root).tokens;
    std::vector<runtime::Rule*> options;
    for (const auto& [quant_id, quant_nodes] : annot->quants_by_name()) {
      for (auto node : quant_nodes) {
        auto quant_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        if (quant_node->stop > quant_node->children.size()) {
          for (auto child : quant_node->children) {
            int child_tokens = node_info.at(child).tokens;
            if (child_tokens > 0 && root_tokens + child_tokens <= limit.tokens) {
              options.push_back(child);
            }
          }
        }
      }
    }
    if (!options.empty()) {
      auto node_to_repeat = options[util::random_int<size_t>(0, options.size() - 1)];
      int max_repeat = limit.tokens != runtime::RuleSize::max().tokens ? (limit.tokens - root_tokens) / node_info.at(node_to_repeat).tokens : 1;
      int repeat = max_repeat > 1 ? util::random_int<int>(1, max_repeat) : 1;
      for (int i = 0; i < repeat; ++i) {
        node_to_repeat->parent->insert_child(util::random_int<size_t>(0, node_to_repeat->parent->children.size() - 1),
                                             node_to_repeat->clone());
      }
      print_mutator("{}: {}, {}", __func__, node_to_repeat->rule_name(), static_cast<runtime::UnparserRuleQuantifier*>(node_to_repeat->parent)->idx);
      return root;
    }

    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Insert copies of a quantified subtree into its quantifier (like
  // replicate_quantified), but regenerate a rule node in each copy.
  runtime::Rule* replicate_with_variation(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();
    const auto& node_info = annot->node_info();

    int root_tokens = node_info.at(root).tokens;
    std::vector<runtime::Rule*> options;
    for (const auto& [quant_id, quant_nodes] : annot->quants_by_name()) {
      for (auto node : quant_nodes) {
        auto quant_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        if (quant_node->stop > quant_node->children.size()) {
          for (auto child : quant_node->children) {
            int child_tokens = node_info.at(child).tokens;
            if (child_tokens > 0 && root_tokens + child_tokens <= limit.tokens) {
              options.push_back(child);
            }
          }
        }
      }
    }
    if (options.empty()) {
      GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
      return nullptr;
    }

    auto node_to_repeat = options[util::random_int<size_t>(0, options.size() - 1)];
    auto parent = static_cast<runtime::UnparserRuleQuantifier*>(node_to_repeat->parent);
    int node_level = node_info.at(node_to_repeat).level;
    int node_tokens = node_info.at(node_to_repeat).tokens;
    int max_repeat = limit.tokens != runtime::RuleSize::max().tokens ? (limit.tokens - root_tokens) / node_tokens : 1;
    int repeat = max_repeat > 1 ? util::random_int<int>(1, max_repeat) : 1;
    int inserted = 0;
    for (int i = 0; i < repeat && root_tokens + node_tokens <= limit.tokens; ++i) {
      auto copy = node_to_repeat->clone();

      // Regenerate a random rule node in each copy to make the copies differ.
      // As regeneration may give back the same tokens (e.g., for literals), a
      // few rule nodes are tried. If none of them changes, no more copies are
      // inserted.
      runtime::Annotations copy_annot(copy);
      const auto& copy_info = copy_annot.node_info();
      std::vector<runtime::Rule*> variants;
      for (const auto& [node_id, nodes] : copy_annot.rules_by_name()) {
        auto rule_size_it = generator_factory._rule_sizes.find(node_id.name);
        if (rule_size_it == generator_factory._rule_sizes.end()) {
          continue;
        }
        for (auto node : nodes) {
          if (node_level + copy_info.at(node).level + rule_size_it->second.depth < limit.depth
              && root_tokens + node_tokens - copy_info.at(node).tokens + rule_size_it->second.tokens < limit.tokens) {
            variants.push_back(node);
          }
        }
      }
      std::shuffle(variants.begin(), variants.end(), util::random_engine);
      bool varied = false;
      for (size_t j = 0; j < variants.size() && j < 3 && !varied; ++j) {
        auto varied_node = variants[j];
        int varied_tokens = copy_info.at(varied_node).tokens;
        auto new_node = generate(varied_node->name, runtime::RuleSize(node_level + copy_info.at(varied_node).level, root_tokens + node_tokens - varied_tokens));
        if (new_node->equalTokens(*varied_node)) {
          delete new_node;
          continue;
        }
        varied_node->replace(new_node);
        delete varied_node;
        root_tokens += node_tokens + runtime::Annotations(new_node).node_info().at(new_node).tokens - varied_tokens;
        varied = true;
      }
      if (!varied) {
        delete copy;
        break;
      }

      parent->insert_child(util::random_int<size_t>(0, parent->children.size() - 1), copy);
      inserted++;
    }
    if (!inserted) {
      GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
      return nullptr;
    }
    print_mutator("{}: {}, {}, {}", __func__, node_to_repeat->rule_name(), parent->idx, inserted);
    return root;
  }

  runtime::Rule* shuffle_quantifieds(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::UnparserRuleQuantifier*> options;
    for (const auto& [quant_id, quant_nodes] : annot->quants_by_name()) {
      for (auto node : quant_nodes) {
        auto quantifier_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        if (quantifier_node->children.size() > 1) {
          options.push_back(quantifier_node);
        }
      }
    }
    if (!options.empty()) {
      auto node_to_shuffle = options[util::random_int<size_t>(0, options.size() - 1)];
      std::shuffle(node_to_shuffle->children.begin(), node_to_shuffle->children.end(), util::random_engine);
      print_mutator("{}: {}, {}", __func__, node_to_shuffle->rule_name(), node_to_shuffle->idx);
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* hoist_rule(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::Rule*> rules = annot->rules();

    if (!rules.empty()) {
      std::shuffle(rules.begin(), rules.end(), util::random_engine);
      for (auto rule_node : rules) {
        auto parent = rule_node->parent;
        while (parent) {
          if (parent->name == rule_node->name && parent != root) {
            print_mutator("{}: {}", __func__, parent->name);
            parent->replace(rule_node);
            delete parent;
            return root;
          }
          parent = parent->parent;
        }
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Repeat the part of the tree between two nodes of the same rule in an
  // ancestor-descendant relationship, nested into each other (the inverse of
  // hoist_rule).
  runtime::Rule* pump_recursion(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();
    const auto& node_info = annot->node_info();

    int root_tokens = node_info.at(root).tokens;
    std::vector<runtime::Rule*> rules = annot->rules();
    std::shuffle(rules.begin(), rules.end(), util::random_engine);
    for (auto rule_node : rules) {
      if (rule_node->type != runtime::Rule::UnparserRuleType) {
        continue;
      }

      std::vector<runtime::Rule*> ancestors;
      for (runtime::Rule* parent = rule_node->parent; parent; parent = parent->parent) {
        if (parent->name == rule_node->name) {
          ancestors.push_back(parent);
        }
      }
      std::shuffle(ancestors.begin(), ancestors.end(), util::random_engine);
      for (auto ancestor : ancestors) {
        // The ring is the part of the ancestor's subtree that is not covered
        // by the descendant. Every pump nests one more copy of the ring
        // between the descendant and its original position.
        int ring_levels = node_info.at(rule_node).level - node_info.at(ancestor).level;
        int ring_tokens = node_info.at(ancestor).tokens - node_info.at(rule_node).tokens;
        int depth_budget = limit.depth - node_info.at(rule_node).level - node_info.at(ancestor).depth;
        if (ring_tokens <= 0 || depth_budget < 0 || root_tokens + ring_tokens > limit.tokens) {
          continue;
        }
        int max_pump = 0;
        if (limit.depth != runtime::RuleSize::max().depth) {
          max_pump = depth_budget / ring_levels + 1;
        }
        if (limit.tokens != runtime::RuleSize::max().tokens) {
          int token_pump = (limit.tokens - root_tokens) / ring_tokens;
          max_pump = max_pump > 0 ? std::min(max_pump, token_pump) : token_pump;
        }
        int pump = max_pump > 1 ? util::random_int<int>(1, max_pump) : 1;

        std::vector<size_t> path;
        for (runtime::Rule* node = rule_node; node != ancestor; node = node->parent) {
          path.push_back(std::find(node->parent->children.begin(), node->parent->children.end(), node) - node->parent->children.begin());
        }
        std::reverse(path.begin(), path.end());

        runtime::Rule* outer_ring = nullptr;
        runtime::Rule* hole = nullptr;
        for (int i = 0; i < pump; ++i) {
          auto ring = ancestor->clone();
          auto ring_hole = ring;
          for (auto idx : path) {
            ring_hole = static_cast<runtime::ParentRule*>(ring_hole)->children[idx];
          }
          if (!outer_ring) {
            outer_ring = ring;
          } else {
            hole->replace(ring);
            delete hole;
          }
          hole = ring_hole;
        }
        rule_node->replace(outer_ring);
        hole->replace(rule_node);
        delete hole;
        print_mutator("{}: {}, {}", __func__, rule_node->name, pump);
        return root;
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* unrestricted_hoist_rule(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::Rule*> rules = annot->rules();

    if (!rules.empty()) {
      std::shuffle(rules.begin(), rules.end(), util::random_engine);
      for (auto rule_node : rules) {
        std::vector<runtime::Rule*> options;
        auto parent = rule_node->parent;
        while (parent && parent != root) {
          if (parent->type == runtime::Rule::UnparserRuleType
              && static_cast<runtime::UnparserRule*>(parent)->children.size() > 1
              && !rule_node->equalTokens(*parent)) {
            options.push_back(parent);
          }
          parent = parent->parent;
        }
        if (!options.empty()) {
            auto hoist_parent = options[util::random_int<size_t>(0, options.size() - 1)];
            print_mutator("{}: {}, {}", __func__, hoist_parent->name, rule_node->name);
            hoist_parent->replace(rule_node);
            delete hoist_parent;
            return root;
        }
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* swap_local_nodes(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::vector<runtime::Rule*>*> options;
    for (auto& [key, nodes] : annot->nodes_by_name()) {
      if (nodes.size() > 1)
        options.push_back(&nodes);
    }
    if (options.size() == 0) {
      GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
      return nullptr;
    }

    const auto& node_info = annot->node_info();
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto nodes : options) {
      std::vector<runtime::Rule*> shuffled(nodes->begin(), nodes->end());
      std::shuffle(shuffled.begin(), shuffled.end(), util::random_engine);

      for (int i = 0; i < shuffled.size() - 1; ++i) {
        auto first_node = shuffled[i];
        int first_node_level = node_info.at(first_node).level;
        int first_node_depth = node_info.at(first_node).depth;
        for (int j = i + 1; j < shuffled.size(); ++j) {
          auto second_node = shuffled[j];
          int second_node_level = node_info.at(second_node).level;
          int second_node_depth = node_info.at(second_node).depth;

          if (first_node_level + second_node_depth > limit.depth
              || second_node_level + first_node_depth > limit.depth) {
            continue;
          }

          // Avoid swapping two identical nodes with each other.
          if (first_node->equalTokens(*second_node)) {
            continue;
          }

          // Ensure the subtrees rooted at recipient and donor nodes are disjunct.
          bool disjunct = true;
          for (auto p = first_node->parent; p && disjunct; p = p->parent) {
            disjunct = p != second_node;
          }
          for (auto p = second_node->parent; p && disjunct; p = p->parent) {
            disjunct = p != first_node;
          }
          if (!disjunct) {
            continue;
          }

          auto first_parent = first_node->parent;
          auto second_parent = second_node->parent;
          *std::find(first_parent->children.begin(), first_parent->children.end(), first_node) = second_node;
          *std::find(second_parent->children.begin(), second_parent->children.end(), second_node) = first_node;
          first_node->parent = second_parent;
          second_node->parent = first_parent;
          print_mutator("{}: {}", __func__, first_node->rule_name());
          return root;
        }
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Replace a node with a copy of another compatible node of the same tree.
  runtime::Rule* copy_local_node(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::vector<runtime::Rule*>*> options;
    for (auto& [key, nodes] : annot->nodes_by_name()) {
      if (nodes.size() > 1)
        options.push_back(&nodes);
    }
    if (options.size() == 0) {
      GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
      return nullptr;
    }

    const auto& node_info = annot->node_info();
    int root_tokens = node_info.at(root).tokens;
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto nodes : options) {
      std::vector<runtime::Rule*> shuffled(nodes->begin(), nodes->end());
      std::shuffle(shuffled.begin(), shuffled.end(), util::random_engine);

      for (auto recipient_node : shuffled) {
        int recipient_node_level = node_info.at(recipient_node).level;
        int recipient_node_tokens = node_info.at(recipient_node).tokens;
        for (auto donor_node : shuffled) {
          if (donor_node == recipient_node
              || recipient_node_level + node_info.at(donor_node).depth > limit.depth
              || root_tokens - recipient_node_tokens + node_info.at(donor_node).tokens > limit.tokens
              || recipient_node->equalTokens(*donor_node)) {
            continue;
          }

          // The donor is cloned before the replacement, so it may be an
          // ancestor or a descendant of the recipient.
          print_mutator("{}: {}", __func__, recipient_node->rule_name());
          recipient_node->replace(donor_node->clone());
          delete recipient_node;
          return root;
        }
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* insert_local_node(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::vector<runtime::Rule*>*> options;
    for (auto& [key, quantifiers] : annot->quants_by_name()) {
      if (quantifiers.size() > 1)
        options.push_back(&quantifiers);
    }
    if (options.size() == 0) {
      GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
      return nullptr;
    }

    const auto& node_info = annot->node_info();
    int root_tokens = node_info.at(root).tokens;
    std::shuffle(options.begin(), options.end(), util::random_engine);
    for (auto quantifiers : options) {
      std::vector<runtime::Rule*> shuffled(quantifiers->begin(), quantifiers->end());
      std::shuffle(shuffled.begin(), shuffled.end(), util::random_engine);

      for (int i = 0; i < shuffled.size() - 1; ++i) {
        auto recipient_node = static_cast<runtime::UnparserRuleQuantifier*>(shuffled[i]);
        if (recipient_node->children.size() >= recipient_node->stop) {
          continue;
        }

        int recipient_node_level = node_info.at(recipient_node).level;
        for (int j = i + 1; j < shuffled.size(); ++j) {
          auto const * const donor_quantifier = static_cast<runtime::UnparserRuleQuantifier*>(shuffled[j]);
          for (auto donor_quantified_node : donor_quantifier->children) {
            if (recipient_node_level + node_info.at(donor_quantified_node).depth <= limit.depth
                && root_tokens + node_info.at(donor_quantified_node).tokens <= limit.tokens) {
              recipient_node->insert_child(recipient_node->children.size() > 0 ? util::random_int<size_t>(0, recipient_node->children.size() - 1) : 0,
                                           donor_quantified_node->clone());
              print_mutator("{}: {}, {}", __func__, recipient_node->rule_name(), recipient_node->idx);
              return root;
            }
          }
        }
      }
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

  // Rewrite all tokens of a lexer rule having the same text to another text of
  // the same lexer rule from the same tree (e.g., rename an identifier).
  runtime::Rule* merge_names(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    // Group the tokens of each lexer rule by their text and keep the lexer
    // rules that have at least two different texts in the tree.
    std::vector<std::map<std::string, std::vector<runtime::UnlexerRule*>>> options;
    for (const auto& [key, nodes] : annot->rules_by_name()) {
      if (key.name.empty() || nodes.front()->type != runtime::Rule::UnlexerRuleType) {
        continue;
      }
      std::map<std::string, std::vector<runtime::UnlexerRule*>> tokens_by_src;
      for (auto node : nodes) {
        auto token = static_cast<runtime::UnlexerRule*>(node);
        if (!token->src.empty()) {
          tokens_by_src[token->src].push_back(token);
        }
      }
      if (tokens_by_src.size() > 1) {
        options.push_back(std::move(tokens_by_src));
      }
    }
    if (options.empty()) {
      GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
      return nullptr;
    }

    const auto& tokens_by_src = options[util::random_int<size_t>(0, options.size() - 1)];
    size_t from_idx = util::random_int<size_t>(0, tokens_by_src.size() - 1);
    size_t to_idx = util::random_int<size_t>(0, tokens_by_src.size() - 2);
    if (to_idx >= from_idx) {
      to_idx++;
    }
    const auto& [from_src, from_tokens] = *std::next(tokens_by_src.begin(), from_idx);
    const auto& to_src = std::next(tokens_by_src.begin(), to_idx)->first;
    print_mutator("{}: {}, {} -> {}", __func__, from_tokens.front()->name, from_src, to_src);
    for (auto token : from_tokens) {
      token->src = to_src;
    }
    return root;
  }

/*
  runtime::Rule* replace_node_random(runtime::Individual* recipient_individual, runtime::Individual* donor_individual) {
    auto recipient_root = recipient_individual->root();
    auto recipient_annot = recipient_individual->annotations();
    const auto& recipient_node_info = recipient_annot->node_info();
    auto donor_annot = donor_individual->annotations();
    const auto& donor_node_info = donor_annot->node_info();

    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> recipient_lookup;
    recipient_lookup.merge(recipient_annot->rules_by_name());
    recipient_lookup.merge(recipient_annot->quants_by_name());
    recipient_lookup.merge(recipient_annot->alts_by_name());

    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> donor_lookup;
    donor_lookup.merge(donor_annot->rules_by_name());
    donor_lookup.merge(donor_annot->quants_by_name());
    donor_lookup.merge(donor_annot->alts_by_name());

    std::vector<runtime::Rule*> recipient_options;
    for (const auto& [key, vec] : recipient_lookup) {
      recipient_options.insert(recipient_options.end(), vec.begin(), vec.end());
    }

    std::vector<runtime::Rule*> donor_options;
    for (const auto& [key, vec] : donor_lookup) {
      donor_options.insert(donor_options.end(), vec.begin(), vec.end());
    }

    std::shuffle(recipient_options.begin(), recipient_options.end(), util::random_engine);
    std::shuffle(donor_options.begin(), donor_options.end(), util::random_engine);
    int recipient_root_tokens = recipient_node_info.at(recipient_root).tokens;
    for (auto recipient_node : recipient_options) {
      if (recipient_node == recipient_root || recipient_node->parent == recipient_root)
        continue;

      int recipient_node_level = recipient_node_info.at(recipient_node).level;
      int recipient_node_tokens = recipient_node_info.at(recipient_node).tokens;

      for (auto donor_node : donor_options) {
        // Make sure that the output tree won't exceed the depth limit.
        if (recipient_node_level + donor_node_info.at(donor_node).depth <= limit.depth
            && recipient_root_tokens - recipient_node_tokens + donor_node_info.at(donor_node).tokens <= limit.tokens) {
          // Cloning is needed since donor_root will be deleted by the caller.

          print_mutator("{}: {}, {}", __func__, recipient_node->name, donor_node->name);
          recipient_node->replace(donor_node->clone());
          // if (recipient_node != recipient_root)
          delete recipient_node;
          return recipient_root;
        }
      }
    }

    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }
*/
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_TOOL_HPP
