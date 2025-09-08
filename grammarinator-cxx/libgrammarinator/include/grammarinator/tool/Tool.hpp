// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_TOOL_HPP
#define GRAMMARINATOR_TOOL_TOOL_HPP

#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../util/print.hpp"
#include "../util/random.hpp"

#include <algorithm>
#include <format>
#include <functional>
#include <iostream>
#include <map>
#include <string>
#include <tuple>
#include <vector>

namespace grammarinator {
namespace tool {

template<class GeneratorFactoryClass>
class Tool {
public:
  using SerializerFn = std::string (*)(const runtime::Rule*);
  using TransformerFn = runtime::Rule* (*)(runtime::Rule*);
  using CreatorFn = std::function<runtime::Rule*(runtime::Individual*, runtime::Individual*)>;

  GeneratorFactoryClass generator_factory;
  std::string rule;
  runtime::RuleSize limit;
  bool unrestricted;
  std::vector<TransformerFn> transformers;
  SerializerFn serializer;
  bool print_mutators;

protected:
  std::map<std::string, CreatorFn> generators;
  std::map<std::string, CreatorFn> mutators;
  std::map<std::string, CreatorFn> recombiners;
  runtime::Population* population;

public:
  explicit Tool(const GeneratorFactoryClass& generator_factory, const std::string& rule = "",
                const runtime::RuleSize& limit = runtime::RuleSize::max(), runtime::Population* population = nullptr, bool unrestricted = true, const std::vector<TransformerFn>& transformers = {},
                SerializerFn serializer = nullptr, bool print_mutators = false)
      : generator_factory(generator_factory), rule(rule), limit(limit), population(population), unrestricted(unrestricted),
        transformers(transformers), serializer(serializer), print_mutators(print_mutators) {
    generators.emplace("generate", [this](auto i1, auto i2) { return generate(); });
    mutators.emplace("regenerate_rule", [this](auto i1, auto i2) { return regenerate_rule(i1); });
    mutators.emplace("delete_quantified", [this](auto i1, auto i2) { return delete_quantified(i1); });
    mutators.emplace("replicate_quantified", [this](auto i1, auto i2) { return replicate_quantified(i1); });
    mutators.emplace("shuffle_quantifieds", [this](auto i1, auto i2) { return shuffle_quantifieds(i1); });
    mutators.emplace("hoist_rule", [this](auto i1, auto i2) { return hoist_rule(i1); });
    mutators.emplace("swap_local_nodes", [this](auto i1, auto i2) { return swap_local_nodes(i1); });
    mutators.emplace("insert_local_node", [this](auto i1, auto i2) { return insert_local_node(i1); });
    recombiners.emplace("replace_node", [this](auto i1, auto i2) { return replace_node(i1, i2); });
    recombiners.emplace("insert_quantified", [this](auto i1, auto i2) { return insert_quantified(i1, i2); });
    if (unrestricted) {
      mutators.emplace("unrestricted_delete", [this](auto i1, auto i2) { return unrestricted_delete(i1); });
      mutators.emplace("unrestricted_hoist_rule", [this](auto i1, auto i2) { return unrestricted_hoist_rule(i1); });
      // recombiners.emplace("replace_node_random", [this](auto i1, auto i2) { return replace_node_random(i1, i2); });  // FIXME: unused?
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
      individual2 = population->select_individual();
    }
    return {individual1, individual2};
  }

  virtual std::map<std::string, CreatorFn>::iterator select_creator(std::map<std::string, CreatorFn>& creators, runtime::Individual* individual1, runtime::Individual* individual2) const  {
    size_t idx = util::random_int<size_t>(0, creators.size() - 1);
    return std::next(creators.begin(), idx);
  }

  runtime::Rule* create_tree(std::map<std::string, CreatorFn>& creators, runtime::Individual* individual1, runtime::Individual* individual2) {
    // Note: creators is potentially modified (creators that return null are removed). Always ensure it is a copy when calling this method.
    runtime::Rule* root = nullptr;

    while (!creators.empty()) {
      auto creatorit = select_creator(creators, individual1, individual2);
      root = creatorit->second(individual1, individual2);
      if (root) {
        break;
      }
      creators.erase(creatorit->first);
    }
    if (!root) {
      root = individual1->root();
    }
    for (const auto& transformer : transformers) {
      root = transformer(root);
    }
    return root;
  }

public:
  runtime::Rule* mutate(runtime::Individual* individual = nullptr) {
    // Regenerate root if it has no children.
    individual = ensure_individual(individual);
    auto root = static_cast<runtime::ParentRule*>(individual->root());
    if (root->children.size() == 0) {
      root->add_child(generate());
      return root;
    } else {
      auto real_root = static_cast<runtime::ParentRule*>(root->children[0]);
      if (real_root->children.empty()) {
        // util::poutf("Regenerate root: {} {}", real_root->name, real_root->type);
        real_root->replace(generate(real_root->name));
        delete real_root;
        return root;
      }
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
    if (print_mutators) {
      std::cout << "GrammarinatorMutator " << std::vformat(fmt, std::make_format_args(args...)) << std::endl;
    }
  }

  runtime::Rule* generate(const std::string& rule_name = "", const runtime::RuleSize& reserve = runtime::RuleSize()) {
    auto generator = generator_factory(limit - reserve);
    std::string rn = !rule_name.empty() ? rule_name : !rule.empty() ? rule : generator_factory._default_rule;
    auto rule_it = generator._rule_fns.find(rn);
    if (rule_it == generator._rule_fns.end()) {
      util::perrf("Rule {} not found.", rn);
      return nullptr;
    }
    print_mutator("[{}] {}", __func__, rn);
    return (generator.*rule_it->second)(nullptr);
  }

  runtime::Rule* regenerate_rule(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();
    const auto& node_info = annot->node_info();

    int root_tokens = node_info.at(root).tokens;
    std::vector<runtime::Rule*> options;
    for (const auto& [node_id, nodes] : annot->rules_by_name()) {
      // TODO: this should be removed or transformed to an assert.
      if (generator_factory._rule_sizes.find(node_id.name) == generator_factory._rule_sizes.end()) {
        util::perrf("!!! {} not found.", node_id.name);
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
      print_mutator("[{}] {}", __func__, mutated_node->name);
      runtime::RuleSize reserve(node_info.at(mutated_node).level,
                                root_tokens - node_info.at(mutated_node).tokens);
      auto new_node = mutated_node->replace(generate(mutated_node->name, reserve));
      delete mutated_node;
      return new_node->root();
    }

    // util::perrf("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* replace_node(runtime::Individual* recipient_individual = nullptr, runtime::Individual* donor_individual = nullptr) {
    auto [ensured_recipient, ensured_donor] = ensure_individuals(recipient_individual, donor_individual);
    auto recipient_root = ensured_recipient->root();
    auto recipient_annot = ensured_recipient->annotations();
    const auto& recipient_node_info = recipient_annot->node_info();
    auto donor_annot = ensured_donor->annotations();
    const auto& donor_node_info = donor_annot->node_info();

    // NOTE: merges clear the data structures of recipient_lookup
    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> recipient_lookup;
    recipient_lookup.merge(recipient_annot->rules_by_name());
    recipient_lookup.merge(recipient_annot->quants_by_name());
    recipient_lookup.merge(recipient_annot->alts_by_name());

    // NOTE: merges clear the data structures of donor_lookup
    std::map<runtime::Annotations::NodeKey, std::vector<runtime::Rule*>> donor_lookup;
    donor_lookup.merge(donor_annot->rules_by_name());
    donor_lookup.merge(donor_annot->quants_by_name());
    donor_lookup.merge(donor_annot->alts_by_name());

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
          print_mutator("[{}] {} {}", __func__, rule_name, recipient_node->name);
          recipient_node->replace(donor_node->clone());
          // TODO: this was originally deleted, but caused SEGV.
          delete recipient_node;
          return recipient_root;
        }
      }
    }

    // util::perrf("{} failed.", __func__);
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
          print_mutator("[{}]", __func__);
          return recipient_root;
        }
      }
    }
    // util::perrf("{} failed.", __func__);
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
      print_mutator("[{}]", __func__);
      removed_node->remove();
      delete removed_node;
      return root;
    }
    // util::perrf("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* unrestricted_delete(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::Rule*> options = annot->rules();

    if (!options.empty()) {
      auto removed_node = options[util::random_int<size_t>(0, options.size() - 1)];
      print_mutator("[{}] {}", __func__, removed_node->name);
      removed_node->remove();
      delete removed_node;
      return root;
    }
    // util::perrf("{} failed.", __func__);
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
      print_mutator("[{}]", __func__);
      return root;
    }

    // util::perrf("{} failed.", __func__);
    return nullptr;
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
      print_mutator("[{}]", __func__);
      return root;
    }
    // util::perrf("{} failed.", __func__);
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
            print_mutator("[{}] {}", __func__, parent->name);
            parent->replace(rule_node);
            delete parent;
            return root;
          }
          parent = parent->parent;
        }
      }
    }
    // util::perrf("{} failed.", __func__);
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
            print_mutator("[{}] {}", __func__, parent->name);
            auto hoist_parent = options[util::random_int<size_t>(0, options.size() - 1)];
            hoist_parent->replace(rule_node);
            delete hoist_parent;
            return root;
        }
      }
    }
    // util::perrf("{} failed.", __func__);
    return nullptr;
  }

  runtime::Rule* swap_local_nodes(runtime::Individual* individual = nullptr) {
    individual = ensure_individual(individual);
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<std::vector<runtime::Rule*>*> options;
    for (auto& [key, nodes] : annot->rules_by_name()) {
      if (nodes.size() > 1)
        options.push_back(&nodes);
    }
    for (auto& [key, nodes] : annot->quants_by_name()) {
      if (nodes.size() > 1)
        options.push_back(&nodes);
    }
    for (auto& [key, nodes] : annot->alts_by_name()) {
      if (nodes.size() > 1)
        options.push_back(&nodes);
    }
    if (options.size() == 0) {
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
              && second_node_level + first_node_depth > limit.depth) {
            continue;
          }

          // Avoid swapping two identical nodes with each other.
          if (first_node->equalTokens(*second_node)) {
            continue;
          }

          // Ensure the subtrees rooted at recipient and donor nodes are disjunct.
          auto const * const upper_node = first_node_level < second_node_level ? first_node : second_node;
          auto const * const lower_node = first_node_level < second_node_level ? second_node : first_node;
          bool disjunct = true;
          auto parent = lower_node->parent;
          while (parent && disjunct) {
            disjunct = parent != upper_node;
            parent = parent->parent;
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
          print_mutator("[{}]", __func__);
          return root;
        }
      }
    }
    // util::perrf("{} failed.", __func__);
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
              print_mutator("[{}]", __func__);
              return root;
            }
          }
        }
      }
    }
    // util::perrf("{} failed.", __func__);
    return nullptr;
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

          print_mutator("[{}] {} -> {}", __func__, recipient_node->name, donor_node->name);
          recipient_node->replace(donor_node->clone());
          // if (recipient_node != recipient_root)
          delete recipient_node;
          return recipient_root;
        }
      }
    }

    // util::perrf("{} failed.", __func__);
    return nullptr;
  }
*/
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_TOOL_HPP
