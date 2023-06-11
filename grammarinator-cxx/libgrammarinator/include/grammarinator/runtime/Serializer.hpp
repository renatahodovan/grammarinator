// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_SERIALIZER_HPP
#define GRAMMARINATOR_RUNTIME_SERIALIZER_HPP

// #include "../util/print.hpp"
#include "Rule.hpp"

#include <string>

namespace grammarinator {
namespace runtime {

inline std::string SimpleSpaceSerializer(const Rule* root) {
  std::string src;
  for (auto it = root->tokens_begin(); it != root->tokens_end(); ++it) {
    const std::string& current_src = *it;
    if (current_src == "<EOF>") {
      continue;
    }
    if (!src.empty()) {
      src += " ";
    }
    src += current_src;
  }
  // grammarinator::util::poutf("SimpleSpaceSerializer: '{}'", src);
  // grammarinator::util::poutf("{:|}{}", *root, src);
  return src;
}

inline std::string NoSpaceSerializer(const Rule* root) {
  std::string src;
  for (auto it = root->tokens_begin(); it != root->tokens_end(); ++it) {
    src += *it;
  }
  return src;
}

} // namespace runtime
} // namespace grammarinator

#endif // GRAMMARINATOR_RUNTIME_SERIALIZER_HPP
