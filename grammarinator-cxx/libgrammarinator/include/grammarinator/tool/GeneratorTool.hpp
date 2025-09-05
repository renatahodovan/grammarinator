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

#include <algorithm>
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
  bool enable_generation;
  bool enable_mutation;
  bool enable_recombination;
  bool keep_trees;
  int unique_attempts;
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
                         int memo_size = 0, int unique_attempts = 2,
                         // bool cleanup = true,
                         // const std::string& encoding = "utf-8",
                         // const std::string& errors = "strict",
                         bool dry_run = false, bool print_mutators = false)
      : Tool<GeneratorFactoryClass>(generator_factory, rule, limit, population, unrestricted, transformers, serializer, memo_size, print_mutators),
        out_format(out_format), enable_generation(generate), enable_mutation(mutate),
        enable_recombination(recombine), keep_trees(keep_trees), unique_attempts(std::max(unique_attempts, 1)),
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
    grammarinator::runtime::Rule* root;
    std::string test;
    for (int attempt = 1; attempt <= unique_attempts; ++attempt) {
      root = create();
      test = this->serializer(root);

      if (this->memoize_test(test.data(), test.size())) {
        break;
      }
      util::poutf("test case #{}, attempt {}/{}: already generated among the last {} unique test cases", index, attempt, unique_attempts, this->memo.size());
      // util::pout(test);
    }

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

      if (this->population && keep_trees) {
        this->population->add_individual(root, test_fn);
      }
    }

    delete root;
    return test_fn;
  }

  runtime::Rule* create() {
    runtime::Individual* individual1 = nullptr;
    runtime::Individual* individual2 = nullptr;
    if (this->population && !this->population->empty()) {
      auto inds = this->ensure_individuals(nullptr, nullptr);
      individual1 = inds.first;
      individual2 = inds.second;
    }

    std::map<std::string, CreatorFn> creators;
    if (enable_generation) {
      creators.insert(this->generators.begin(), this->generators.end());
    }
    if (this->population && !this->population->empty()) {
      if (enable_mutation) {
        creators.insert(this->mutators.begin(), this->mutators.end());
      }
      if (enable_recombination) {
        creators.insert(this->recombiners.begin(), this->recombiners.end());
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
