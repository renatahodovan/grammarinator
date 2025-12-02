// Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

// This custom unparser is used by Custom.g4

#ifndef CUSTOMSUBCLASSGENERATOR_HPP
#define CUSTOMSUBCLASSGENERATOR_HPP

#include "CustomGenerator.hpp"


class CustomSubclassGenerator : public CustomGenerator {
private:
  int cnt{0};

public:
  explicit CustomSubclassGenerator(Model* model=new DefaultModel(),
                                   const std::vector<Listener*>& listeners={},
                                   const RuleSize& limit=RuleSize::max())
      : CustomGenerator(model, listeners, limit) {}

  Rule* tagname(Rule *parent = nullptr) override {
    cnt++;

    UnparserRuleContext rule(this, "tagname", parent);
    UnparserRule* current = static_cast<UnparserRule*>(rule.current());
    current->add_child(new UnlexerRule("ID", "customtag"));
    return current;
  }

  std::string _custom_lexer_content() override {
    assert(cnt > 0);
    return "custom content";
  }
};

#endif // CUSTOMSUBCLASSGENERATOR_HPP
