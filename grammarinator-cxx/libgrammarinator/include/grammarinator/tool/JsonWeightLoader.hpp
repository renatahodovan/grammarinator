// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_JSONWEIGHTLOADER_HPP
#define GRAMMARINATOR_TOOL_JSONWEIGHTLOADER_HPP

#include <filesystem>

#include <nlohmann/json.hpp>

namespace grammarinator {
namespace tool {

class JsonWeightLoader {
public:
  JsonWeightLoader() = default;
  JsonWeightLoader(const JsonWeightLoader& other) = delete;
  JsonWeightLoader& operator=(const JsonWeightLoader& other) = delete;
  JsonWeightLoader(JsonWeightLoader&& other) = delete;
  JsonWeightLoader& operator=(JsonWeightLoader&& other) = delete;

  void load(const std::string& fn, runtime::WeightedModel::WeightMap& weights) {
    std::ifstream wf(fn);
    if (!wf) {
      util::perrf("Failed to open the weights JSON file for reading: {}", fn);
      return;
    }

    nlohmann::json data = nlohmann::json::parse(wf, nullptr, false);
    if (data.is_discarded()) {
      util::perrf("Invalid JSON in weights file: {}", fn);
      return;
    }

    for (auto& [rule, alts] : data.items()) {
      for (auto& [alternation_idx, alternatives] : alts.items()) {
          for (auto& [alternative_idx, w] : alternatives.items()) {
            weights[{rule, static_cast<size_t>(std::stoul(alternation_idx)), static_cast<size_t>(std::stoul(alternative_idx))}] = w.get<double>();
          }
      }
    }
  }
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_JSONWEIGHTLOADER_HPP
