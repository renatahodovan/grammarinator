// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_LIBFUZZERTOOL_HPP
#define GRAMMARINATOR_TOOL_LIBFUZZERTOOL_HPP

#include "../runtime/Population.hpp"
#include "../runtime/Rule.hpp"
#include "../util/log.hpp"
#include "../util/random.hpp"
#include "FlatBuffersTreeCodec.hpp"
#include "Tool.hpp"
#include "TreeCodec.hpp"

#include <algorithm>
#include <cstring>
#include <memory>
#include <string>
#include <vector>

extern "C" size_t LLVMFuzzerMutate(uint8_t* Data, size_t Size, size_t MaxSize);

namespace grammarinator {
namespace tool {

class LastMutationCache {
private:
  std::vector<uint8_t> data_;
  std::unique_ptr<runtime::Rule> root_;

public:
  void store(const uint8_t* data, size_t size, runtime::Rule* root) {
    if (!root_ || root_.get() != root) {
      root_.reset(root);
    }
    data_.assign(data, data + size);
  }

  void store_without_delete(const uint8_t* data, size_t size, runtime::Rule* root) {
    root_.release();
    root_.reset(root);
    data_.assign(data, data + size);
  }

  runtime::Rule* load(const uint8_t* data, size_t size) {
    if (!root_ || size != data_.size() || !std::equal(data_.begin(), data_.end(), data)) {
      return nullptr;
    }

    return root_.get();
  }
};

template<class GeneratorFactoryClass>
class LibFuzzerTool : public Tool<GeneratorFactoryClass> {
public:
  using SerializerFn = typename Tool<GeneratorFactoryClass>::SerializerFn;
  using TransformerFn = typename Tool<GeneratorFactoryClass>::TransformerFn;

private:
  const TreeCodec& codec;
  // Single per-instance temporary buffer reused by custom mutator and
  // crossover. Resize before use to the requested max size to avoid repeated
  // allocations across frequent calls.
  std::vector<uint8_t> tmp_buf_;

public:
  explicit LibFuzzerTool(const GeneratorFactoryClass& generator_factory, const std::string& rule = "",
                         const runtime::RuleSize& limit = runtime::RuleSize::max(),
                         bool unrestricted = true,
                         const std::unordered_set<std::string> allowlist = {}, const std::unordered_set<std::string> blocklist = {},
                         const std::vector<TransformerFn>& transformers = {}, SerializerFn serializer = nullptr,
                         int memo_size = 0, const TreeCodec& codec = FlatBuffersTreeCodec())
      : Tool<GeneratorFactoryClass>(generator_factory, rule, limit, nullptr,
                                    true, true, true, unrestricted, allowlist, blocklist,
                                    transformers, serializer, memo_size),
        codec(codec) {
    if (unrestricted) {
      this->allow_creator(this->mutators, "libfuzzer_mutate", [this](auto i1, auto i2) { return libfuzzer_mutate(i1); });
    }
  }

  LibFuzzerTool(const LibFuzzerTool& other) = delete;
  LibFuzzerTool& operator=(const LibFuzzerTool& other) = delete;
  LibFuzzerTool(LibFuzzerTool&& other) = delete;
  LibFuzzerTool& operator=(LibFuzzerTool&& other) = delete;
  ~LibFuzzerTool() override = default;

  std::string one_input(const uint8_t* data, size_t size) {
    auto root = getCache()->load(data, size);
    bool cache_hit = root != nullptr;
    if (!cache_hit) {
      root = decode(data, size);
      // if (root) {
      //   getCache()->store(data, size, root);
      // }
      if (!root) {
        GRAMMARINATOR_LOG_WARN("Decode of {} sized input failed.", size);
        return "";
      }
    }
    std::string test = this->serializer(root);
    if (!cache_hit)
      delete root;

    return test;
  }

  size_t custom_mutator(uint8_t* data, size_t size, size_t maxsize, unsigned int seed) {
    util::random_engine.seed(seed);

    auto root = getCache()->load(data, size);
    bool cache_hit = root != nullptr;
    if (!cache_hit)
      root = decode(data, size);

    runtime::Individual individual(root, false);
    auto mutated_root = this->mutate(&individual);
    // Encode into a temporary buffer first instead of writing directly into
    // `data`. This avoids a transient mismatch between `data` contents and the
    // reported size when the mutator is invoked repeatedly; the encoded bytes
    // are commited into `data` only after memoization accepts the candidate.
    tmp_buf_.resize(std::max<size_t>(1, maxsize));
    size_t outsize = this->codec.encode(mutated_root, tmp_buf_.data(), maxsize);
    if (outsize == 0) {
      GRAMMARINATOR_LOG_WARN("Mutation failed, result could not be encoded");
      return 0;
    }
    if (!this->memoize_test(tmp_buf_.data(), outsize)) {
      GRAMMARINATOR_LOG_DEBUG("Mutation attempt: already generated among the last {} unique test cases", this->memo.size());
      GRAMMARINATOR_LOG_TRACE("Duplicate test case: {}", this->serializer(mutated_root));
      return 0;
    }

    std::memcpy(data, tmp_buf_.data(), outsize);

    if (cache_hit && root != mutated_root) {
      // if mutated_root != root, then this->mutate(root) has completely replaced
      // and deleted root already, so the cache must not call delete on the root
      // again
      getCache()->store_without_delete(data, outsize, mutated_root);
    } else {
      getCache()->store(data, outsize, mutated_root);
    }
    return outsize;
  }

  size_t custom_cross_over(const uint8_t* data1, size_t size1, const uint8_t* data2, size_t size2, uint8_t* out,
                           size_t maxoutsize, unsigned int seed) {
    util::random_engine.seed(seed);

    auto recipient_root = getCache()->load(data1, size1);
    bool cache_hit = recipient_root != nullptr;
    if (!cache_hit)
      recipient_root = decode(data1, size1);
    auto donor_root = decode(data2, size2);

    runtime::Individual recipient_individual(recipient_root, false), donor_individual(donor_root, false);
    auto cross_over_root = this->recombine(&recipient_individual, &donor_individual);
    // Use temporal buffer similar to custom_mutator.
    tmp_buf_.resize(std::max<size_t>(1, maxoutsize));
    size_t outsize = this->codec.encode(cross_over_root, tmp_buf_.data(), maxoutsize);
    if (outsize == 0) {
      GRAMMARINATOR_LOG_WARN("Crossover failed, result could not be encoded");
      return 0;
    }

    if (!this->memoize_test(tmp_buf_.data(), outsize)) {
      GRAMMARINATOR_LOG_DEBUG("Crossover attempt: already generated among the last {} unique test cases", this->memo.size());
      GRAMMARINATOR_LOG_TRACE("Duplicate test case: '{}'", this->serializer(cross_over_root));
      return 0;
    }

    std::memcpy(out, tmp_buf_.data(), outsize);

    if (cache_hit && recipient_root != cross_over_root) {
      getCache()->store_without_delete(out, outsize, cross_over_root);
    } else {
      // if (!decode_success && recipient_root != cross_over_root && recipient_root != donor_root && recipient_root)
      //   delete recipient_root;
      getCache()->store(out, outsize, cross_over_root);
    }
    delete donor_root;
    return outsize;
  }

  runtime::Rule* libfuzzer_mutate(runtime::Individual* individual) {
    auto root = individual->root();
    auto annot = individual->annotations();

    std::vector<runtime::UnlexerRule*> options;
    for (const auto& [node_key, nodes] : annot->rules_by_name()) {
      for (auto node : nodes) {
        if (node->type == runtime::Rule::UnlexerRuleType) {
          options.push_back(static_cast<runtime::UnlexerRule*>(node));
        }
      }
    }
    if (!options.empty()) {
      auto node_to_mutate = options[util::random_int<size_t>(0, options.size() - 1)];
      std::string value = node_to_mutate->src;
      std::string result = value;
      int new_size = value.size() + 50;
      result.resize(std::max(1, new_size));
      result.resize(LLVMFuzzerMutate(reinterpret_cast<uint8_t*>(&result[0]), value.size(), result.size()));
      this->print_mutator("{}: {}", __func__, node_to_mutate->name);
      node_to_mutate->src = result;
      return root;
    }
    GRAMMARINATOR_LOG_TRACE("{} failed.", __func__);
    return nullptr;
  }

private:
  runtime::Rule* decode(const uint8_t* data, size_t size) const {
    auto root = codec.decode(data, size);
    if (root) {
      if (root->name == "<ROOT>") {
        return root;
      }
      auto new_root = new runtime::UnparserRule("<ROOT>");
      new_root->add_child(root);
      return new_root;
    }
    auto new_root = new runtime::UnparserRule("<ROOT>");
    new_root->add_child(new runtime::UnparserRule(this->rule));
    return new_root;
  }

  LastMutationCache* getCache() {
    static LastMutationCache cache;
    return &cache;
  }
};

}  // namespace tool
}  // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_LIBFUZZERTOOL_HPP
