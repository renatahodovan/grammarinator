// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_NLOHMANNJSONTREECODEC_HPP
#define GRAMMARINATOR_TOOL_NLOHMANNJSONTREECODEC_HPP

#include "../util/print.hpp"
#include "TreeCodec.hpp"

#include <climits>
#include <cstring>
#include <nlohmann/json.hpp>
#include <string>

namespace grammarinator {
namespace tool {

class NlohmannJsonTreeCodec : public TreeCodec {
public:
  NlohmannJsonTreeCodec() = default;
  NlohmannJsonTreeCodec(const NlohmannJsonTreeCodec& other) = delete;
  NlohmannJsonTreeCodec& operator=(const NlohmannJsonTreeCodec& other) = delete;
  NlohmannJsonTreeCodec(NlohmannJsonTreeCodec&& other) = delete;
  NlohmannJsonTreeCodec& operator=(NlohmannJsonTreeCodec&& other) = delete;
  ~NlohmannJsonTreeCodec() override = default;

  std::vector<uint8_t> encode(runtime::Rule* root) const override {
    std::string str = toJson(root).dump(-1, ' ', true, nlohmann::detail::error_handler_t::ignore);
    return std::vector<uint8_t>(str.data(), str.data() + str.size());
  }

  size_t encode(runtime::Rule* root, uint8_t* buffer, size_t maxsize) const override {
    std::string str = toJson(root).dump(-1, ' ', true, nlohmann::detail::error_handler_t::ignore);
    size_t size = str.size();
    if (size <= maxsize) {
      std::memcpy(buffer, str.data(), size);
      return size;
    }
    util::perrf("Output size is out of range ({} > {})", size, maxsize);
    return 0;
  }

  runtime::Rule* decode(const uint8_t* buffer, size_t size) const override {
    std::string src(reinterpret_cast<const char*>(buffer), size);
    auto jsonObj = nlohmann::json::parse(src, nullptr, false);
    // if (jsonObj.is_discarded()) {
    //   util::perrf("codec error on data of size {} '{}'", size, src);
    // }
    return !jsonObj.is_discarded() ? fromJson(jsonObj) : nullptr;
  }

private:
  nlohmann::json toJson(runtime::Rule* node) const {
    nlohmann::json j;

    if (node->type == runtime::Rule::UnlexerRuleType) {
      const auto* unlexer_node = static_cast<runtime::UnlexerRule*>(node);
      j["t"] = "l";  // "UnlexerRule"
      j["n"] = node->name;
      j["s"] = unlexer_node->src;
      j["z"] = nlohmann::json::array({unlexer_node->size.depth, unlexer_node->size.tokens});
      j["i"] = unlexer_node->immutable;
    } else {
      if (node->type == runtime::Rule::UnparserRuleType) {
        j["t"] = "p";  // "UnparserRule"
        j["n"] = node->name;
      } else if (node->type == runtime::Rule::UnparserRuleAlternativeType) {
        const auto* alt_node = static_cast<runtime::UnparserRuleAlternative*>(node);
        j["t"] = "a";  // "UnparserRuleAlternative"
        j["ai"] = alt_node->alt_idx;
        j["i"] = alt_node->idx;
      } else if (node->type == runtime::Rule::UnparserRuleQuantifiedType) {
        j["t"] = "qd";  // "UnparserRuleQuantified"
      } else if (node->type == runtime::Rule::UnparserRuleQuantifierType) {
        const auto* quant_node = static_cast<runtime::UnparserRuleQuantifier*>(node);
        j["t"] = "q";  // "UnparserRuleQuantifier"
        j["i"] = quant_node->idx;
        j["b"] = quant_node->start;
        j["e"] = quant_node->stop != INT_MAX ? quant_node->stop : -1;
      }
      j["c"] = nlohmann::json::array();
      for (const auto& child : static_cast<runtime::UnparserRule*>(node)->children) {
        j["c"].push_back(toJson(child));
      }
    }
    return j;
  }

  runtime::Rule* fromJson(const nlohmann::json& obj) const {
    if (obj["t"] == "l") {
      auto size = obj["z"].get<std::vector<int>>();
      return new runtime::UnlexerRule(obj["n"].get<std::string>(), obj["s"].get<std::string>(), runtime::RuleSize(size[0], size[1]), obj["i"]);
    }
    runtime::ParentRule* node{};
    if (obj["t"] == "p") {
      node = new runtime::UnparserRule(obj["n"].get<std::string>());
    } else if (obj["t"] == "a") {
      node = new runtime::UnparserRuleAlternative(obj["ai"].get<int>(), obj["i"].get<int>());
    } else if (obj["t"] == "qd") {
      node = new runtime::UnparserRuleQuantified();
    } else if (obj["t"] == "q") {
      int end = obj["e"].get<int>();
      node = new runtime::UnparserRuleQuantifier(obj["i"].get<int>(), obj["b"].get<int>(), end != -1 ? end : INT_MAX);
    }
    if (!obj["c"].empty()) {
      for (const auto& child : obj["c"]) {
        node->add_child(fromJson(child));
      }
    }
    return node;
  }
};

} // namespace tool
} // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_NLOHMANNJSONTREECODEC_HPP
