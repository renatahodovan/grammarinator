// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_DEFAULTGENERATORFACTORY_HPP
#define GRAMMARINATOR_TOOL_DEFAULTGENERATORFACTORY_HPP

#include "../runtime/DefaultModel.hpp"
#include "../runtime/Listener.hpp"
#include "../runtime/Model.hpp"
#include "../runtime/Rule.hpp"
#include "../runtime/WeightedModel.hpp"
#include "GeneratorFactory.hpp"

#include <vector>

namespace grammarinator {
namespace tool {

template<class GeneratorClass, class ModelClass = runtime::DefaultModel, class... ListenerClasses>
class DefaultGeneratorFactory : public GeneratorFactory<GeneratorClass> {
private:
  runtime::WeightedModel::AltMap weights;
  runtime::WeightedModel::QuantMap probs;

public:
  explicit DefaultGeneratorFactory(const runtime::WeightedModel::AltMap& weights = {}, const runtime::WeightedModel::QuantMap& probs = {})
      : weights(weights), probs(probs) {}

  GeneratorClass operator()(const runtime::RuleSize& limit = runtime::RuleSize::max()) {
    runtime::Model* model = new ModelClass();
    if (!weights.empty() || !probs.empty()) {
      model = new runtime::WeightedModel(model, weights, probs);
    }
    std::vector<runtime::Listener*> listeners = {(new ListenerClasses())...};
    return GeneratorClass(model, listeners, limit);
  }
};

} // namespace tool
} // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_DEFAULTGENERATORFACTORY_HPP
