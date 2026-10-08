// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
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
#include <format>
#include <fstream>
#include <regex>
#include <string>
#include <utility>
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
  // Rewrite named placeholders to positional ones (as expected by
  // std::vformat) and build the regex that recovers the first placeholder
  // (usually {id}) from the names created by the pattern.
  static std::pair<std::string, std::string> positional_fmtstr(const std::string& fmtstr, const std::vector<std::string>& fields) {
    static const std::regex special_re(R"([\\^$.|?*+()\[\]{}])");

    std::string field_re_str = R"(\{\{|\}\}|\{()";
    bool first_field = true;
    for (const auto& field : fields) {
      if (!first_field) {
        field_re_str += "|";
      }
      field_re_str += field;
      first_field = false;
    }
    field_re_str += R"()(:[^{}]*)?\})";
    std::regex field_re(field_re_str);

    std::string rewritten;
    std::string regex;
    std::string suffix = fmtstr;
    bool has_first_field = false;

    for (std::sregex_iterator it(fmtstr.cbegin(), fmtstr.cend(), field_re), end; it != end; ++it) {
      const std::smatch& field = *it;
      rewritten += field.prefix().str();
      regex += std::regex_replace(field.prefix().str(), special_re, R"(\$&)");
      if (!field[1].matched) {  // Escaped brace.
        rewritten += field.str();
        regex += R"(\)" + field.str().substr(1);
      } else {
        auto field_index = std::distance(fields.begin(), std::find(fields.begin(), fields.end(), field[1].str()));
        rewritten += "{" + std::to_string(field_index) + field[2].str() + "}";
        if (field_index == 0) {
          regex += has_first_field ? R"(\1)" : "(.*?)";
          has_first_field = true;
        } else {
          regex += ".*?";
        }
      }
      suffix = field.suffix().str();
    }
    rewritten += suffix;
    regex += std::regex_replace(suffix, special_re, R"(\$&)");

    return {rewritten, regex};
  }

  std::string out_format;
  std::filesystem::path out_dir;
  std::string out_name;  // Filename pattern with positional placeholders: {0}=id, {1}=src, {2}=op.
  std::regex src_regex;  // Matches the names created by out_name, capturing their id (if any).
  bool keep_trees;
  int unique_attempts;
  // bool cleanup;
  // std::string encoding;
  // std::string errors;
  bool dry_run;

public:
  explicit GeneratorTool(const GeneratorFactoryClass& generator_factory, const std::string& out_format,
                         const std::string& rule = "", const runtime::RuleSize& limit = runtime::RuleSize::max(),
                         runtime::Population* population = nullptr, bool keep_trees = false,
                         bool generate = true, bool mutate = true, bool recombine = true, bool unrestricted = true,
                         const std::unordered_set<std::string> allowlist = {}, const std::unordered_set<std::string> blocklist = {},
                         const std::vector<TransformerFn>& transformers = {}, SerializerFn serializer = nullptr,
                         int memo_size = 0, int unique_attempts = 2,
                         // bool cleanup = true,
                         // const std::string& encoding = "utf-8",
                         // const std::string& errors = "strict",
                         bool dry_run = false)
      : Tool<GeneratorFactoryClass>(generator_factory, rule, limit, population,
                                    generate, mutate, recombine, unrestricted,
                                    allowlist, blocklist,
                                    transformers, serializer,
                                    memo_size),
        out_format(out_format), keep_trees(keep_trees), unique_attempts(std::max(unique_attempts, 1)),
        // cleanup(cleanup), encoding(encoding), errors(errors),
        dry_run(dry_run) {
    if (!out_format.empty()) {
      std::filesystem::path out_path(out_format);
      out_dir = out_path.parent_path();

      // Convert the legacy %d placeholder to {id}.
      std::string name = out_path.filename().string();
      if (const auto pos = name.find("%d"); pos != std::string::npos) {
        name.replace(pos, 2, "{id}");
      }

      auto [rewritten_name, regex] = positional_fmtstr(name, {"id", "src", "op"});
      out_name = rewritten_name;
      src_regex = std::regex(regex);

      // Fail early on invalid patterns.
      int id = 0;
      std::string none = "-";
      (void)std::vformat(out_name, std::make_format_args(id, none, none));

      if (!dry_run && !out_dir.empty()) {
        std::filesystem::create_directories(out_dir);
      }
    }
  }

  GeneratorTool(const GeneratorTool& other) = delete;
  GeneratorTool& operator=(const GeneratorTool& other) = delete;
  GeneratorTool(GeneratorTool&& other) = delete;
  GeneratorTool& operator=(GeneratorTool&& other) = delete;
  ~GeneratorTool() override = default;

  std::string create_test(int index) {
    grammarinator::runtime::Rule* root = nullptr;
    std::string test;
    for (int attempt = 1; attempt <= unique_attempts; ++attempt) {
      root = create();
      if (!root) {
        GRAMMARINATOR_LOG_WARN("Test case #{} attempt {}/{}: could not be generated.", index, attempt);
        continue;
      }
      test = this->serializer(root);

      if (this->memoize_test(test.data(), test.size())) {
        break;
      }
      GRAMMARINATOR_LOG_DEBUG("Test case #{}, attempt {}/{}: already generated among the last {} unique test cases", index, attempt, unique_attempts, this->memo.size());
      GRAMMARINATOR_LOG_TRACE("Duplicate test case: '{}'", test);
      delete root;
      root = nullptr;
    }

    if (!root) {
      return "";
    }

    std::string test_fn;
    if (!dry_run) {
      if (!out_format.empty()) {
        std::string src = this->last_individual;
        if (std::smatch match; std::regex_match(src, match, src_regex) && match.size() > 1) {
          src = match[1].str();
        }
        if (src.empty()) {
          src = "-";
        }
        std::string op = !this->last_mutator.empty() ? this->last_mutator : "-";
        test_fn = (out_dir / std::vformat(out_name, std::make_format_args(index, src, op))).string();

        std::ofstream file(test_fn, std::ios::binary);
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
    creators.insert(this->generators.begin(), this->generators.end());
    if (this->population && !this->population->empty()) {
      creators.insert(this->mutators.begin(), this->mutators.end());
      creators.insert(this->recombiners.begin(), this->recombiners.end());
    }
    auto root = this->create_tree(creators, individual1, individual2);
    // Mutation and recombination have loaded individual1 and may return its root.
    // Clone that root before deleting individual1; generation needs no such check.
    if (individual1 && root && !this->generators.contains(this->last_mutator) && individual1->root() == root) {
      root = root->clone();
    }
    delete individual1;
    delete individual2;
    return root;
  }
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_GENERATORTOOL_HPP
