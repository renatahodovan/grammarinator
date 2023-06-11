// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
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
  runtime::WeightedModel::WeightMap weights;

public:
  explicit DefaultGeneratorFactory(const runtime::WeightedModel::WeightMap& weights = {})
      : weights(weights) {}

  GeneratorClass operator()(const runtime::RuleSize& limit = runtime::RuleSize::max()) {
    runtime::Model* model = new ModelClass();
    if (!weights.empty()) {
      model = new runtime::WeightedModel(model, weights);
    }
    std::vector<runtime::Listener*> listeners = {(new ListenerClasses())...};
    return GeneratorClass(model, listeners, limit);
  }
};

} // namespace tool
} // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_DEFAULTGENERATORFACTORY_HPP
