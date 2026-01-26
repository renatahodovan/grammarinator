// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
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

  void load(const std::string& fn, runtime::WeightedModel::AltMap& weights, runtime::WeightedModel::QuantMap& probs) {
    std::ifstream wf(fn);
    if (!wf) {
      GRAMMARINATOR_LOG_FATAL("Failed to open the weights JSON file for reading: {}", fn);
      return;
    }

    nlohmann::json data = nlohmann::json::parse(wf, nullptr, false);
    if (data.is_discarded()) {
      GRAMMARINATOR_LOG_FATAL("Invalid JSON in weights file: {}", fn);
      return;
    }

    if (data.contains("alts") && data["alts"].is_object()) {
      for (auto& [rule, alts] : data["alts"].items()) {
        for (auto& [alternation_idx, alternatives] : alts.items()) {
          for (auto& [alternative_idx, w] : alternatives.items()) {
            weights[{rule, static_cast<size_t>(std::stoul(alternation_idx)), static_cast<size_t>(std::stoul(alternative_idx))}] = w.get<double>();
          }
        }
      }
    }
    if (data.contains("quants") && data["quants"].is_object()) {
      for (auto& [rule, quants] : data["quants"].items()) {
        for (auto& [quantifier_idx, quant] : quants.items()) {
          probs[{rule, static_cast<size_t>(std::stoul(quantifier_idx))}] = quant.get<double>();
        }
      }
    }
  }
};

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_JSONWEIGHTLOADER_HPP
