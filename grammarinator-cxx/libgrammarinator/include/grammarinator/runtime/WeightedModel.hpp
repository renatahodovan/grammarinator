// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_WEIGHTEDMODEL_HPP
#define GRAMMARINATOR_RUNTIME_WEIGHTEDMODEL_HPP

#include "Model.hpp"

#include <map>
#include <string>
#include <tuple>

namespace grammarinator {
namespace runtime {

/*
 * Custom model (or model wrapper) that pre-multiplies the weights of
 * alternatives before calling the underlying model.
 */
class WeightedModel : public Model {
public:
  using WeightMapKey = std::tuple<std::string, size_t, size_t>;
  using WeightMap = std::map<WeightMapKey, double>;

private:
  Model* model;
  const WeightMap& weights;

public:
  explicit WeightedModel(Model* model, const WeightMap& weights = {}) noexcept : Model(), model(model), weights(weights) {}
  WeightedModel(const WeightedModel& other) = delete;
  WeightedModel& operator=(const WeightedModel& other) = delete;
  WeightedModel(WeightedModel&& other) = delete;
  WeightedModel& operator=(WeightedModel&& other) = delete;
  ~WeightedModel() override { delete model; }

  int choice(const Rule* node, int idx, const std::vector<double>& cweights) override {
    std::vector<double> multiplied_weights(cweights.size());
    for (size_t i = 0; i < cweights.size(); ++i) {
      auto it = weights.find(WeightMapKey(node->name, idx, i));
      multiplied_weights[i] = cweights[i] * (it != weights.end() ? it->second : 1.0);
    }
    return model->choice(node, idx, multiplied_weights);
  }

  bool quantify(const Rule* node, int idx, int cnt, int start, int stop) override {
    return model->quantify(node, idx, cnt, start, stop);
  }

  std::string charset(const Rule* node, int idx, const std::vector<std::string>& chars) override {
    return model->charset(node, idx, chars);
  }
};

} // namespace runtime
} // namespace grammarinator

#endif // GRAMMARINATOR_RUNTIME_WEIGHTEDMODEL_HPP
