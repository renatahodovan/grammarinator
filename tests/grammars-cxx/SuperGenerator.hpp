// Copyright (c) 2019-2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

// This custom superclass is used by SuperClass.g4 and SuperClassOption.g4

#ifndef SUPERGENERATOR_HPP
#define SUPERGENERATOR_HPP

#include <grammarinator/runtime.hpp>

class SuperGenerator : public grammarinator::runtime::Generator {
public:
  explicit SuperGenerator(grammarinator::runtime::Model* model=new grammarinator::runtime::DefaultModel(),
                          const std::vector<grammarinator::runtime::Listener*>& listeners={},
                          const grammarinator::runtime::RuleSize& limit=grammarinator::runtime::RuleSize::max())
      : Generator(model, listeners, limit) {}

  grammarinator::runtime::Rule* InheritedRule(grammarinator::runtime::Rule *parent = nullptr) {
    auto current = new grammarinator::runtime::UnlexerRule("InheritedRule", "I was inherited.");
    if (parent) {
      static_cast<grammarinator::runtime::ParentRule*>(parent)->add_child(current);
    }
    return current;
  }
};

#endif // SUPERGENERATOR_HPP
