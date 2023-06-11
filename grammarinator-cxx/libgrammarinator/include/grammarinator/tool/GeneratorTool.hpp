// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_GENERATORTOOL_HPP
#define GRAMMARINATOR_TOOL_GENERATORTOOL_HPP

#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../util/print.hpp"
#include "Tool.hpp"

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace grammarinator {
namespace tool {

template<class GeneratorFactoryClass>
class GeneratorTool : public Tool<GeneratorFactoryClass> {
public:
  using SerializerFn = typename Tool<GeneratorFactoryClass>::SerializerFn;
  using TransformerFn = typename Tool<GeneratorFactoryClass>::TransformerFn;
  using CreatorFn = typename Tool<GeneratorFactoryClass>::CreatorFn;

private:
  std::string out_format;
  runtime::Population* population;
  bool enable_generation;
  bool enable_mutation;
  bool enable_recombination;
  bool keep_trees;
  // bool cleanup;
  // std::string encoding;
  // std::string errors;
  bool dry_run;

public:
  explicit GeneratorTool(const GeneratorFactoryClass& generator_factory, const std::string& out_format,
                         const std::string& rule = "", const runtime::RuleSize& limit = runtime::RuleSize::max(),
                         runtime::Population* population = nullptr, bool generate = true, bool mutate = true,
                         bool recombine = true, bool unrestricted = true, bool keep_trees = false,
                         const std::vector<TransformerFn>& transformers = {}, SerializerFn serializer = nullptr,
                         // bool cleanup = true,
                         // const std::string& encoding = "utf-8",
                         // const std::string& errors = "strict",
                         bool dry_run = false, bool print_mutators = false)
      : Tool<GeneratorFactoryClass>(generator_factory, rule, limit, unrestricted, transformers, serializer, print_mutators),
        out_format(out_format), population(population), enable_generation(generate), enable_mutation(mutate),
        enable_recombination(recombine), keep_trees(keep_trees),
        // cleanup(cleanup), encoding(encoding), errors(errors),
        dry_run(dry_run) {
    if (!out_format.empty() && !dry_run) {
      std::filesystem::path directoryPath = std::filesystem::absolute(std::filesystem::path(out_format).parent_path());

      if (!std::filesystem::exists(directoryPath))
        std::filesystem::create_directories(directoryPath);
    }
  }

  GeneratorTool(const GeneratorTool& other) = delete;
  GeneratorTool& operator=(const GeneratorTool& other) = delete;
  GeneratorTool(GeneratorTool&& other) = delete;
  GeneratorTool& operator=(GeneratorTool&& other) = delete;
  ~GeneratorTool() override = default;

  std::string create_test(int index) {
    auto root = create();
    std::string test = this->serializer(root);

    std::string test_fn;
    if (!dry_run) {
      if (!out_format.empty()) {
        test_fn = out_format;
        size_t pos = test_fn.find("%d");
        if (pos != std::string::npos) {
          test_fn.replace(pos, 2, std::to_string(index));
        }
        std::ofstream file(test_fn);
        file << test;
        file.close();
      } else {
        util::pout(test);
      }

      if (population && keep_trees) {
        population->add_individual(root, test_fn);
      }
    }

    delete root;
    return test_fn;
  }

  runtime::Rule* create() {
    runtime::Individual* individual1 = nullptr;
    runtime::Individual* individual2 = nullptr;
    if (population && !population->empty()) {
      individual1 = population->select_individual();
      individual2 = population->select_individual();
    }

    std::vector<CreatorFn> creators;
    if (enable_generation) {
      creators.insert(creators.end(), this->generators.begin(), this->generators.end());
    }
    if (population && !population->empty()) {
      if (enable_mutation) {
        creators.insert(creators.end(),this->mutators.begin(), this->mutators.end());
      }
      if (enable_recombination) {
        creators.insert(creators.end(), this->recombiners.begin(), this->recombiners.end());
      }
    }
    auto root = this->create_tree(creators, individual1, individual2);
    if (individual1 && individual1->root() == root) {
      root = root->clone();  // FIXME: this is expensive
    }
    if (individual1) delete individual1;
    if (individual2) delete individual2;
    return root;
  }
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_GENERATORTOOL_HPP
