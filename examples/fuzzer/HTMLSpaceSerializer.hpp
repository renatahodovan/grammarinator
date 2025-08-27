// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef HTMLSPACESERIALIZER_HPP
#define HTMLSPACESERIALIZER_HPP

#include "grammarinator/runtime/Rule.hpp"

#include <stack>
#include <string>
#include <utility>
#include <vector>

inline std::string HTMLSpaceSerializer(const Rule* root) {
  std::string src;
  std::stack<std::pair<const Rule*, const Rule*>> stack;
  stack.push({root, nullptr});  // (node, right_sibling)

  while (!stack.empty()) {
    const Rule* node = stack.top().first;
    const Rule* right_sibling = stack.top().second;
    stack.pop();

    if (node->type == Rule::UnlexerRuleType) {
      const std::string& text = static_cast<const UnlexerRule*>(node)->src;
      if (text.starts_with("<script")) {
        src += "<script " + text.substr(7);
      } else if (text.starts_with("<style")) {
        src += "<style " + text.substr(6);
      } else if (text.starts_with("<?xml")) {
        src += "<?xml " + text.substr(5);
      } else {
        src += text;
      }
    } else {
      // Whitespace logic for unparser rules
      if (node->type == Rule::UnparserRuleType) {
        const std::string& name = node->name;
        if ((name == "htmlTagName" && right_sibling && right_sibling->name == "htmlAttribute") ||
            name == "htmlAttribute") {
          src += ' ';
        }
      }

      // Push children in reverse order with right_sibling info
      const auto& children = static_cast<const ParentRule*>(node)->children;
      const size_t n = children.size();
      for (size_t i = 0; i < n; ++i) {
        const Rule* child = children[n - 1 - i];
        const Rule* rs = (n - i < n) ? children[n - i] : nullptr;
        stack.push({child, rs});
      }
    }
  }

  return src;
}

#endif // HTMLSPACESERIALIZER_HPP
