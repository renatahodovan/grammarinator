// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

// This subclassed generator is used by ImagToken.g4

#ifndef IMAGTOKENSUBCLASSGENERATOR_HPP
#define IMAGTOKENSUBCLASSGENERATOR_HPP

#include "ImagTokenGenerator.hpp"


class ImagTokenSubclassGenerator : public ImagTokenGenerator {
public:
  explicit ImagTokenSubclassGenerator(Model* model=new DefaultModel(),
                                      const std::vector<Listener*>& listeners={},
                                      const RuleSize& limit=RuleSize::max())
      : ImagTokenGenerator(model, listeners, limit) {}

  Rule* REDEFINED(Rule* parent = nullptr) override {
    UnlexerRuleContext rule(this, "REDEFINED", parent);
    UnlexerRule* current = static_cast<UnlexerRule*>(rule.current());
    current->src += "redefined";
    return current;
  }
};

#endif // IMAGTOKENSUBCLASSGENERATOR_HPP
