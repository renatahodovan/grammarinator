// Copyright (c) 2026 Renata Hodovan.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef LIBFUZZER_BUFFERS_TESTS_HPP
#define LIBFUZZER_BUFFERS_TESTS_HPP

#include <grammarinator/runtime.hpp>
#include <grammarinator/tool/DefaultGeneratorFactory.hpp>
#include <grammarinator/tool/LibFuzzerTool.hpp>

#include <cassert>
#include <memory>

// Stand in for libFuzzer's byte mutator with a deterministic, observable edit.
extern "C" size_t LLVMFuzzerMutate(uint8_t* data, size_t size, size_t maxsize) {
  assert(maxsize == size + 50);
  data[size] = '!';
  return size + 1;
}

// Check output bytes and failure atomicity across changing buffer limits.
template<class Generator>
static void test_libfuzzer_buffers() {
  using namespace grammarinator;
  using namespace runtime;
  using Factory = tool::DefaultGeneratorFactory<Generator>;
  tool::FlatBuffersTreeCodec codec;
  tool::LibFuzzerTool<Factory> tool(Factory(), "start", {12, 40}, true, {"libfuzzer_mutate"}, {}, {}, NoSpaceSerializer, 4, codec);
  auto root = std::make_unique<UnparserRule>("start");
  root->add_child(new UnlexerRule("TOKEN", std::string(2048, 'a'), {1, 1}, false));
  auto encoded = codec.encode(root.get());
  auto buffer = encoded;
  buffer.resize(16384, 0xaa);
  size_t size = tool.custom_mutator(buffer.data(), encoded.size(), buffer.size(), 42);
  assert(size > 0 && tool.one_input(buffer.data(), size) == std::string(2048, 'a') + "!");
  auto previous = buffer;
  assert(tool.custom_mutator(buffer.data(), size, 1, 42) == 0);
  assert(buffer == previous);
  assert(tool.custom_mutator(buffer.data(), size, 0, 42) == 0);
  assert(buffer == previous);
  std::copy(encoded.begin(), encoded.end(), buffer.begin());
  previous = buffer;
  assert(tool.custom_mutator(buffer.data(), encoded.size(), buffer.size(), 42) == 0);
  assert(buffer == previous);
  // A new input must work after both oversized and duplicate candidates.
  static_cast<UnlexerRule*>(root->children[0])->src = "b";
  encoded = codec.encode(root.get());
  std::copy(encoded.begin(), encoded.end(), buffer.begin());
  size = tool.custom_mutator(buffer.data(), encoded.size(), 1024, 43);
  assert(size > 0 && tool.one_input(buffer.data(), size) == "b!");
}

#endif  // LIBFUZZER_BUFFERS_TESTS_HPP
