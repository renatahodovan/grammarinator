// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#include "grlf.h"

#include <grammarinator/runtime.hpp>
#include <grammarinator/tool.hpp>
#include <grammarinator/util/print.hpp>
#include <grammarinator/util/random.hpp>

#include <cstring>
#include <string>
#include <vector>

#include "grammarinator/config.hpp"

namespace {

struct {
  bool print_test = false;
  bool print_mutators = false;
  bool random_mutators = true;
  int max_tokens = 0;
  int max_depth = 0;
  int memo_size = 0;
  runtime::WeightedModel::WeightMap weights;
} settings;

void initialize_int_arg(const std::string& arg, const std::string& name, int& dest) {
  std::string prefix = "-" + name + "=";
  if (arg.rfind(prefix, 0) == 0) {
    std::string suffix = arg.substr(prefix.length());
    char* endp;
    long value = std::strtol(suffix.c_str(), &endp, 10);
    if (endp - suffix.c_str() == suffix.length()) {
      dest = (int)value;
      grammarinator::util::poutf("{} set to {}", name, dest);
    } else {
      grammarinator::util::perrf("invalid value for {}: {}", name, suffix);
    }
  }
}

void initialize_bool_arg(const std::string& arg, const std::string& name, bool& dest) {
  std::string prefix = "-" + name + "=";
  if (arg.rfind(prefix, 0) == 0) {
    std::string suffix = arg.substr(prefix.length());
    char* endp;
    long value = std::strtol(suffix.c_str(), &endp, 10);
    if (endp - suffix.c_str() == suffix.length()) {
      dest = (bool)value;
      grammarinator::util::poutf("{} set to {}", name, dest);
    } else {
      grammarinator::util::perrf("invalid value for {}: {}", name, suffix);
    }
  }
}

void initialize_double_arg(const std::string& arg, const std::string& name, double& dest) {
  std::string prefix = "-" + name + "=";
  if (arg.rfind(prefix, 0) == 0) {
    std::string suffix = arg.substr(prefix.length());
    char* endp;
    double value = std::strtod(suffix.c_str(), &endp);
    if (endp - suffix.c_str() == suffix.length()) {
      dest = value;
      grammarinator::util::poutf("{} set to {}", name, dest);
    } else {
      grammarinator::util::perrf("invalid value for {}: {}", name, suffix);
    }
  }
}

void initialize_weights_arg(const std::string& arg, const std::string& name, runtime::WeightedModel::WeightMap& weights) {
  std::string prefix = "-" + name + "=";
  if (arg.rfind(prefix, 0) == 0) {
    std::string weights_path = arg.substr(prefix.length());
    JsonWeightLoader().load(weights_path, weights);
  }
}

grammarinator::tool::LibFuzzerTool<grammarinator::tool::DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER>>*
libfuzzer_tool() {
  static const GRAMMARINATOR_TREECODEC treeCodec;
  static grammarinator::tool::LibFuzzerTool<grammarinator::tool::DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER>>
  tool(grammarinator::tool::DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER>(settings.weights),
       GRAMMARINATOR_GENERATOR::_default_rule,
       grammarinator::runtime::RuleSize(settings.max_depth > 0 ? settings.max_depth : grammarinator::runtime::RuleSize::max().depth,
                                        settings.max_tokens > 0 ? settings.max_tokens : grammarinator::runtime::RuleSize::max().tokens),
       settings.random_mutators,
       GRAMMARINATOR_TRANSFORMER ? std::vector<grammarinator::runtime::Rule* (*)(grammarinator::runtime::Rule*)>{GRAMMARINATOR_TRANSFORMER} : std::vector<grammarinator::runtime::Rule* (*)(grammarinator::runtime::Rule*)>{},
       GRAMMARINATOR_SERIALIZER,
       settings.memo_size,
       treeCodec,
       settings.print_mutators);

  return &tool;
}

}  // namespace

// Command line processing

extern "C"
int GrammarinatorInitialize(int* argc, char*** argv) {
  if (argc == nullptr || argv == nullptr) {
    return 1;
  }
  bool ignore_remaining_args = false;

  for (int i = 0; i < *argc; ++i) {
    if (std::strcmp((*argv)[i], "-ignore_remaining_args=1") == 0) {
      ignore_remaining_args = true;
    } else if (ignore_remaining_args) {
      initialize_bool_arg((*argv)[i], "print_test", settings.print_test);
      initialize_bool_arg((*argv)[i], "print_mutators", settings.print_mutators);
      initialize_bool_arg((*argv)[i], "random_mutators", settings.random_mutators);
      initialize_int_arg((*argv)[i], "max_tokens", settings.max_tokens);
      initialize_int_arg((*argv)[i], "max_depth", settings.max_depth);
      initialize_int_arg((*argv)[i], "memo_size", settings.memo_size);
      initialize_weights_arg((*argv)[i], "weights", settings.weights);
    }
  }
  return 0;
}

// Blackbox Grammarinator on top of LibFuzzer:
// - whatever input comes from the LibFuzzer harness, it is overwritten by a
//   newly generated test case
// - no mutation or crossover at all
// - LibFuzzer is only utilized to transport the input to the target and track
//   the progress (i.e., change of coverage, found bugs)

extern "C"
size_t GrammarinatorGenerator(uint8_t* Data, size_t Size, size_t MaxSize, unsigned int Seed) {
  grammarinator::util::random_engine.seed(Seed);
  auto tool = libfuzzer_tool();
  auto root = tool->generate();
  std::string test = tool->serializer(root);
  if (settings.print_test)
    grammarinator::util::pout(test);
  delete root;
  Size = test.size();
  Size = Size < MaxSize ? Size : MaxSize;
  std::memcpy(Data, test.c_str(), Size);
  return Size;
}

// Grammarinator driven by LibFuzzer:
// - inputs must be in tree format (seed corpus must be parsed in advance)
// - both mutators and crossovers of LibFuzzer are replaced by the algorithms of
//   Grammaranator
// - corpus is managed by LibFuzzer

extern "C"
size_t GrammarinatorMutator(uint8_t* Data, size_t Size, size_t MaxSize, unsigned int Seed) {
  return libfuzzer_tool()->custom_mutator(Data, Size, MaxSize, Seed);
}

extern "C"
size_t GrammarinatorCrossOver(uint8_t* Data1, size_t Size1, const uint8_t* Data2, size_t Size2,
                              uint8_t* Out, size_t MaxOutSize, unsigned int Seed) {
  return libfuzzer_tool()->custom_cross_over(Data1, Size1, Data2, Size2, Out, MaxOutSize, Seed);
}

extern "C"
void GrammarinatorOneInput(const uint8_t** Data, size_t* Size) {
  static std::string input;

  input = libfuzzer_tool()->one_input(*Data, *Size);
  if (settings.print_test)
    grammarinator::util::pout(input);
  *Data = reinterpret_cast<const uint8_t*>(input.c_str());
  *Size = input.size();
}
