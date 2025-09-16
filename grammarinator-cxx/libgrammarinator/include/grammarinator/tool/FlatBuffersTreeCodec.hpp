// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_FLATBUFFERSTREECODEC_HPP
#define GRAMMARINATOR_TOOL_FLATBUFFERSTREECODEC_HPP

#include "../util/print.hpp"
#include "TreeCodec.hpp"

#define FLATBUFFERS_DEBUG_VERIFICATION_FAILURE
#include "grammarinator/tool/fbs/FBRule_generated.h"

#include <cstring>
#include <string>

namespace grammarinator {
namespace tool {

class FlatBuffersTreeCodec : public TreeCodec {
public:
  FlatBuffersTreeCodec() = default;
  FlatBuffersTreeCodec(const FlatBuffersTreeCodec& other) = delete;
  FlatBuffersTreeCodec& operator=(const FlatBuffersTreeCodec& other) = delete;
  FlatBuffersTreeCodec(FlatBuffersTreeCodec&& other) = delete;
  FlatBuffersTreeCodec& operator=(FlatBuffersTreeCodec&& other) = delete;
  ~FlatBuffersTreeCodec() override = default;

  std::vector<uint8_t> encode(runtime::Rule* root) const override {
    flatbuffers::FlatBufferBuilder builder;
    builder.Finish(buildFBRule(builder, root));

    const uint8_t* buf = builder.GetBufferPointer();
    size_t size = builder.GetSize();
    return std::vector<uint8_t>(buf, buf + size);
  }

  size_t encode(runtime::Rule* root, uint8_t* buffer, size_t maxsize) const override {
    flatbuffers::FlatBufferBuilder builder;
    builder.Finish(buildFBRule(builder, root));

    const uint8_t* buf = builder.GetBufferPointer();
    size_t size = builder.GetSize();
    if (size <= maxsize) {
      std::memcpy(buffer, buf, size);
      return size;
    }
    util::perrf("Output size is out of range ({} > {})", size, maxsize);
    return 0;
  }

  runtime::Rule* decode(const uint8_t* buffer, size_t size) const override {
    if (size < FLATBUFFERS_MIN_BUFFER_SIZE)
      return nullptr;
    flatbuffers::Verifier verifier(buffer, size, {512, 1000000, false, false, FLATBUFFERS_MAX_BUFFER_SIZE, true});
    if (fbs::VerifyFBRuleBuffer(verifier)) {
      return readFBRule(fbs::GetFBRule(buffer));
    }
    util::perrf("Flatbuffer verification failed (maxsize: {}).", size);
    return nullptr;
  }

private:
  flatbuffers::Offset<fbs::FBRule> buildFBRule(flatbuffers::FlatBufferBuilder& builder, const runtime::Rule* rule) const {
    if (rule->type == runtime::Rule::UnlexerRuleType) {
      auto fbName = builder.CreateString(rule->name.c_str(), rule->name.size());
      const auto* unlexer_rule = static_cast<const runtime::UnlexerRule*>(rule);
      auto fbSrc = builder.CreateString(unlexer_rule->src.c_str(), unlexer_rule->src.size());
      fbs::FBRuleBuilder fbrule_builder(builder);
      fbrule_builder.add_type(fbs::FBRuleType_UnlexerRuleType);
      fbrule_builder.add_name(fbName);
      fbrule_builder.add_src(fbSrc);
      auto fbsize = fbs::FBRuleSize(unlexer_rule->size.depth, unlexer_rule->size.tokens);
      fbrule_builder.add_size(&fbsize);
      fbrule_builder.add_immutable(unlexer_rule->immutable);
      return fbrule_builder.Finish();
    }

    const auto* parent_rule = static_cast<const runtime::ParentRule*>(rule);
    std::vector<flatbuffers::Offset<fbs::FBRule>> children;
    children.reserve(parent_rule->children.size());
    for (const auto* child : parent_rule->children) {
      children.push_back(buildFBRule(builder, child));
    }
    auto fbchildren = builder.CreateVector(children);
    flatbuffers::Offset<flatbuffers::String> fbName;
    if (rule->type == runtime::Rule::UnparserRuleType)
      fbName = builder.CreateString(rule->name.c_str(), rule->name.size());
    fbs::FBRuleBuilder fbrule_builder(builder);
    fbrule_builder.add_children(fbchildren);

    if (rule->type == runtime::Rule::UnparserRuleType) {
      fbrule_builder.add_name(fbName);
      fbrule_builder.add_type(fbs::FBRuleType_UnparserRuleType);
    } else if (rule->type == runtime::Rule::UnparserRuleQuantifierType) {
      const auto* unparser_quantifier = static_cast<const runtime::UnparserRuleQuantifier*>(rule);
      fbrule_builder.add_type(fbs::FBRuleType_UnparserRuleQuantifierType);
      fbrule_builder.add_idx(unparser_quantifier->idx);
      fbrule_builder.add_start(unparser_quantifier->start);
      fbrule_builder.add_stop(unparser_quantifier->stop == INT_MAX ? -1 : unparser_quantifier->stop);
    } else if (rule->type == runtime::Rule::UnparserRuleQuantifiedType) {
      fbrule_builder.add_type(fbs::FBRuleType_UnparserRuleQuantifiedType);
    } else if (rule->type == runtime::Rule::UnparserRuleAlternativeType) {
      const auto* unparser_alternative = static_cast<const runtime::UnparserRuleAlternative*>(rule);
      fbrule_builder.add_type(fbs::FBRuleType_UnparserRuleAlternativeType);
      fbrule_builder.add_alt_idx(unparser_alternative->alt_idx);
      fbrule_builder.add_idx(unparser_alternative->idx);
    }
    return fbrule_builder.Finish();
  }

  runtime::Rule* readFBRule(const fbs::FBRule* fbrule) const {
    if (fbrule->type() == fbs::FBRuleType_UnlexerRuleType) {
      const auto* fbsize = fbrule->size();
      return new runtime::UnlexerRule(std::string(fbrule->name()->c_str(), fbrule->name()->size()),
                                      std::string(fbrule->src()->c_str(), fbrule->src()->size()),
                                      runtime::RuleSize(fbsize->depth(), fbsize->tokens()),
                                      fbrule->immutable());
    } else {
      runtime::ParentRule* parent_rule{};
      if (fbrule->type() == fbs::FBRuleType_UnparserRuleType) {
        parent_rule = new runtime::UnparserRule(std::string(fbrule->name()->c_str(), fbrule->name()->size()));
      } else if (fbrule->type() == fbs::FBRuleType_UnparserRuleQuantifierType) {
        int stop = fbrule->stop();
        parent_rule = new runtime::UnparserRuleQuantifier(fbrule->idx(), fbrule->start(), stop == -1 ? INT_MAX : stop);
      } else if (fbrule->type() == fbs::FBRuleType_UnparserRuleQuantifiedType) {
        parent_rule = new runtime::UnparserRuleQuantified();
      } else if (fbrule->type() == fbs::FBRuleType_UnparserRuleAlternativeType) {
        parent_rule = new runtime::UnparserRuleAlternative(fbrule->alt_idx(), fbrule->idx());
      }

      for (const auto* fbchild : *fbrule->children()) {
        parent_rule->add_child(readFBRule(fbchild));
      }
      return parent_rule;
    }
  }
};

} // namespace tool
} // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_FLATBUFFERSTREECODEC_HPP
