// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_DEFAULTMODEL_HPP
#define GRAMMARINATOR_RUNTIME_DEFAULTMODEL_HPP

#include "../util/random.hpp"
#include "Model.hpp"

#include <numeric>

namespace grammarinator {
namespace runtime {

class DefaultModel : public Model {
public:
  DefaultModel() = default;
  DefaultModel(const DefaultModel& other) = delete;
  DefaultModel& operator=(const DefaultModel& other) = delete;
  DefaultModel(DefaultModel&& other) = delete;
  DefaultModel& operator=(DefaultModel&& other) = delete;
  ~DefaultModel() override = default;

  int choice(const Rule* node, int idx, const std::vector<double>& weights) override {
    // Calculate the total sum of weights
    double sum = std::accumulate(weights.begin(), weights.end(), 0.0);
    if (sum == 0) {
      // Return the last alternative if no choice was made
      return weights.size() - 1;
    }
    return grammarinator::util::random_weighted_choice(weights);
  }

  bool quantify(const Rule* node, int idx, int cnt, int start, int stop, double prob = 0.5) override {
    return grammarinator::util::random_real(0.0, 1.0) < prob;
  }

  std::string charset(const Rule* node, int idx, const std::vector<std::string>& chars) override {
    return chars[grammarinator::util::random_int<size_t>(0, chars.size() - 1)];
  }
};

} // namespace runtime
} // namespace grammarinator

#endif // GRAMMARINATOR_RUNTIME_DEFAULTMODEL_HPP
