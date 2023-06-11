// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_GENERATORFACTORY_HPP
#define GRAMMARINATOR_TOOL_GENERATORFACTORY_HPP

#include "../runtime/DefaultModel.hpp"
#include "../runtime/Rule.hpp"

namespace grammarinator {
namespace tool {

template<class GeneratorClass>
class GeneratorFactory {
public:
  decltype((GeneratorClass::_default_rule)) _default_rule{GeneratorClass::_default_rule};
  decltype((GeneratorClass::_rule_sizes)) _rule_sizes{GeneratorClass::_rule_sizes};
  decltype((GeneratorClass::_alt_sizes)) _alt_sizes{GeneratorClass::_alt_sizes};
  decltype((GeneratorClass::_quant_sizes)) _quant_sizes{GeneratorClass::_quant_sizes};

  GeneratorFactory() = default;

  GeneratorClass operator()(const runtime::RuleSize& limit = runtime::RuleSize::max()) {
    return GeneratorClass(new runtime::DefaultModel(), {}, limit);
  }
};

} // namespace tool
} // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_GENERATORFACTORY_HPP
