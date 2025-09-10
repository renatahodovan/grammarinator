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
#include "../util/print.hpp"
#include "../util/random.hpp"
#include "FlatBuffersTreeCodec.hpp"
#include "Tool.hpp"
#include "TreeCodec.hpp"

#include <algorithm>
#include <memory>
#include <string>
#include <vector>

extern "C" size_t LLVMFuzzerMutate(uint8_t* Data, size_t Size, size_t MaxSize);

namespace grammarinator {
namespace tool {

class LibFuzzerIndividual : public runtime::Individual {
private:
  runtime::Rule* root_;

public:
  explicit LibFuzzerIndividual(runtime::Rule* root) : runtime::Individual(""), root_(root) { }
  LibFuzzerIndividual(const LibFuzzerIndividual& other) = delete;
  LibFuzzerIndividual& operator=(const LibFuzzerIndividual& other) = delete;
  LibFuzzerIndividual(LibFuzzerIndividual&& other) = delete;
  LibFuzzerIndividual& operator=(LibFuzzerIndividual&& other) = delete;
  ~LibFuzzerIndividual() override = default;  // NOTE: do NOT delete root!

  runtime::Rule* root() override { return root_; }
};

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

public:
  explicit LibFuzzerTool(const GeneratorFactoryClass& generator_factory, const std::string& rule = "",
                         const runtime::RuleSize& limit = runtime::RuleSize::max(), bool unrestricted = true, const std::vector<TransformerFn>& transformers = {},
                         SerializerFn serializer = nullptr, const TreeCodec& codec = FlatBuffersTreeCodec(),
                         bool print_mutators = false)
      : Tool<GeneratorFactoryClass>(generator_factory, rule, limit, nullptr, unrestricted, transformers, serializer, print_mutators), codec(codec) {
    if (unrestricted) {
      this->mutators.emplace("libfuzzer_mutate", [this](auto i1, auto i2) { return libfuzzer_mutate(i1); });
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
        util::perr("decode failed");
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
    // bool decode_success = false;
    if (!cache_hit) {
      root = decode(data, size);
      // decode_success = root != nullptr;
      if (!root) {
        auto new_root = new runtime::UnparserRule("<ROOT>");
        new_root->add_child(new runtime::UnparserRule(this->rule));
        root = new_root;
      }
    }
    if (root->name != "<ROOT>") {
        // util::pout("root is not artificial");
        auto new_root = new runtime::UnparserRule("<ROOT>");
        new_root->add_child(root);
        root = new_root;
    }

    if (static_cast<runtime::ParentRule*>(root)->children.size() == 0)
        util::poutf("!!! root has no children: {}, cache_hit: {}", root->name, cache_hit);

    // util::poutf("MUTATE({})\n---------------\n{}", size, this->serializer(root));

    runtime::Rule* mutated_root = nullptr;
    size_t outsize = 0;
    do {
      LibFuzzerIndividual individual(root);
      mutated_root = this->mutate(&individual);
      outsize = this->codec.encode(mutated_root, data, maxsize);
      if (outsize == 0)
        util::pout("!!! mutation failed, result could not been encoded");
    } while (outsize == 0);

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
    // bool decode_success = false;
    if (!cache_hit) {
      recipient_root = decode(data1, size1);
      // decode_success = recipient_root != nullptr;
      if (!recipient_root) {
        auto new_recipient_root = new runtime::UnparserRule("<ROOT>");
        new_recipient_root->add_child(new runtime::UnparserRule(this->rule));
        recipient_root = new_recipient_root;
      }
    }
    auto donor_root = decode(data2, size2);
    if (!donor_root) {
      auto new_donor_root = new runtime::UnparserRule("<ROOT>");
      new_donor_root->add_child(new runtime::UnparserRule(this->rule));
      donor_root = new_donor_root;
    }

    runtime::Rule* cross_over_root = nullptr;
    size_t outsize = 0;
    // size_t sanity_size = this->codec.encode(recipient_root, out, maxoutsize);
    // if (sanity_size == 0)
    //   util::poutf("!!! encoded recipient_root is too large: cache_hit: {}, decode_success: {}, size1: {}", cache_hit, decode_success, size1);
    // assert(sanity_size > 0);

    // TODO: this do-while causes infinite loop in some cases which causes libfuzzer
    // size_t idx = 0;
    do {
      // sanity_size = this->codec.encode(recipient_root, out, maxoutsize);
      // if (sanity_size == 0)
      //   util::poutf("!!! Recipient size is insufficient in #{} iteration !!!", idx);
      // assert(sanity_size > 0);
      LibFuzzerIndividual recipient_individual(recipient_root), donor_individual(donor_root);
      cross_over_root = this->recombine(&recipient_individual, &donor_individual);
      outsize = this->codec.encode(cross_over_root, out, maxoutsize);
      // if (outsize == 0)
      //   util::poutf("#{}. outsize is 0 after cross-over\nRESULT:{}\nRECIPIENT:{}\nDONOR:{}", idx, this->serializer(cross_over_root), this->serializer(recipient_root), this->serializer(donor_root));
      // idx += 1;
    } while (outsize == 0);

    // util::poutf("++++++++++++++\n{}", this->serializer(cross_over_root));
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
    // util::pout(__func__);
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
      this->print_mutator("[{}]", __func__);
      node_to_mutate->src = result;
      return root;
    }
    // util::perrf("{} failed.", __func__);
    return nullptr;
  }

private:
  runtime::Rule* decode(const uint8_t* data, size_t size) const {
    if (size < 2) {
      // util::poutf("too small data to decode: {}", size);
      // auto root = new runtime::UnparserRule(this->rule);
      // util::perrf("codec error on data of size {}", size);
      return nullptr;
    }

    // util::pout(data);
    // util::pout(size);
    auto root = codec.decode(data, size);
    if (!root) {
      // root = new runtime::UnparserRule(this->rule);
      // if (size > 1) {
      //   util::perrf("codec error on data of size {}", size);
      // }
    }
    return root;
  }

  LastMutationCache* getCache() {
    static LastMutationCache cache;
    return &cache;
  }
};

}  // namespace tool
}  // namespace grammarinator

#endif  // GRAMMARINATOR_TOOL_LIBFUZZERTOOL_HPP
