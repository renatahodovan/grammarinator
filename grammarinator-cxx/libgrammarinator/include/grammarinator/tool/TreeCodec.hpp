// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_TREECODEC_HPP
#define GRAMMARINATOR_TOOL_TREECODEC_HPP

#include "../runtime/Rule.hpp"

#include <cstdint>
#include <cstring>
#include <vector>

namespace grammarinator {
namespace tool {

class TreeCodec {
public:
  TreeCodec() = default;
  TreeCodec(const TreeCodec& other) = delete;
  TreeCodec& operator=(const TreeCodec& other) = delete;
  TreeCodec(TreeCodec&& other) = delete;
  TreeCodec& operator=(TreeCodec&& other) = delete;
  virtual ~TreeCodec() = default;

  virtual std::vector<uint8_t> encode(runtime::Rule* root) const = 0;

  virtual size_t encode(runtime::Rule* root, uint8_t* buffer, size_t maxsize) const {
    std::vector<uint8_t> vec = encode(root);
    std::memcpy(buffer, vec.data(), vec.size() <= maxsize ? vec.size() : maxsize);
    return vec.size();
  }

  virtual runtime::Rule* decode(const uint8_t* buffer, size_t size) const = 0;

  virtual runtime::Rule* decode(const std::vector<uint8_t>& buffer) const { return decode(buffer.data(), buffer.size()); }
};

} // namespace tool
} // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_TREECODEC_HPP
