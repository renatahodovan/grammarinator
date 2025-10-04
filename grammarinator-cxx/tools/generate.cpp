// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#include <grammarinator/runtime.hpp>
#include <grammarinator/tool.hpp>
#include <grammarinator/util/print.hpp>
#include <grammarinator/util/random.hpp>

#include <cxxopts.hpp>

#include <filesystem>
#include <map>
#include <random>
#include <string>
#include <tuple>

#include "grammarinator/config.hpp"

using namespace grammarinator::runtime;
using namespace grammarinator::tool;
using namespace grammarinator::util;

template<class T>
TreeCodec* treecodec_factory() { return new T(); }

static const std::map<std::string, std::tuple<std::string, TreeCodec*(*)()>> tree_formats = {
  {"flatbuffers", {"grtf", treecodec_factory<FlatBuffersTreeCodec>}},
  {"json", {"grtj", treecodec_factory<JsonTreeCodec>}},
};

int main(int argc, char **argv) {
  std::string tree_format_choices;
  bool first_format = true;
  for (const auto& tree_format : tree_formats) {
    if (!first_format) {
      tree_format_choices += ", ";
    }
    tree_format_choices += tree_format.first;
    first_format = false;
  }

  try {
    cxxopts::Options options(argv[0], "Grammarinator: Generate (with C++)");
    options.add_options()
      ("r,rule",
       "name of the rule to start generation from (default: the parser rule set by grammarinator-process)",
       cxxopts::value<std::string>(),
       "NAME")
      ("d,max-depth",
       "maximum recursion depth during generation",
       cxxopts::value<int>()->default_value(std::to_string(RuleSize::max().depth)),
       "NUM")
      ("max-tokens",
       "maximum token number during generation",
       cxxopts::value<int>()->default_value(std::to_string(RuleSize::max().tokens)),
       "NUM")
      ("p,population",
       "directory of grammarinator tree pool",
       cxxopts::value<std::string>(),
       "DIR")
      ("no-generate",
       "disable test generation from grammar",
       cxxopts::value<bool>()->default_value("false"))
      ("no-mutate",
       "disable test generation by mutation (disabled by default if no population is given)",
       cxxopts::value<bool>()->default_value("false"))
      ("no-recombine",
       "disable test generation by recombination (disabled by default if no population is given)",
       cxxopts::value<bool>()->default_value("false"))
      ("no-grammar-violations",
       "disable applying grammar-violating mutators (enabled by default)",
       cxxopts::value<bool>()->default_value("false"))
      ("keep-trees",
       "keep generated tests to participate in further mutations or recombinations (only if population is given)",
       cxxopts::value<bool>()->default_value("false"))
      ("tree-format",
       "format of the serialized trees (choices: " + tree_format_choices + ")",
       cxxopts::value<std::string>()->default_value("flatbuffers"),
       "NAME")
      ("o,out",
       "output file name pattern",
       cxxopts::value<std::string>()->default_value((std::filesystem::current_path() / "tests" / "test_%d").string()),
       "FILE")
      ("stdout",
       "print test cases to stdout (alias for --out='')",
       cxxopts::value<bool>())
      ("n",
       "number of tests to generate",
       cxxopts::value<int>()->default_value("1"),
       "NUM")
      ("memo-size",
       "memoize the last NUM unique tests; if a memoized test case is generated again, it is discarded and generation of a unique test case is retried",
       cxxopts::value<int>()->default_value("0"),
       "NUM"
      )
      ("unique-attempts",
       "limit on how many times to try to generate a unique (i.e., non-memoized) test case; no effect if --memo-size=0",
       cxxopts::value<int>()->default_value("2"),
       "NUM"
      )
      ("random-seed",
       "initialize random number generator with fixed seed (not set by default)",
       cxxopts::value<int>(),
       "NUM")
      ("dry-run",
       "generate tests without writing them to file or printing to stdout (do not keep generated tests in population either)",
       cxxopts::value<bool>()->default_value("false"))
      ("version", "print version and exit")
      ("help", "print help and exit")
      ;
    auto args = options.parse(argc, argv);

    if (args.count("help")) {
      pout(options.help());
      exit(0);
    }
    if (args.count("version")) {
      poutf("{} {}", argv[0], GRAMMARINATOR_STRFY(GRAMMARINATOR_VERSION));
      poutf("generator: {}", GRAMMARINATOR_STRFY(GRAMMARINATOR_GENERATOR));
      poutf("model: {}", GRAMMARINATOR_STRFY(GRAMMARINATOR_MODEL));
      poutf("listener: {}", GRAMMARINATOR_STRFY(GRAMMARINATOR_LISTENER));
      poutf("transformer: {}", GRAMMARINATOR_STRFY(GRAMMARINATOR_TRANSFORMER));
      poutf("serializer: {}", GRAMMARINATOR_STRFY(GRAMMARINATOR_SERIALIZER));
      exit(0);
    }

    auto tree_format_it = tree_formats.find(args["tree-format"].as<std::string>());
    if (tree_format_it == tree_formats.end()) {
      throw cxxopts::exceptions::parsing("Invalid argument for option 'tree-format'");
    }
    std::string tree_extension = std::get<0>(tree_format_it->second);
    TreeCodec* tree_codec = std::get<1>(tree_format_it->second)();

    int seed = args.count("random-seed") ? args["random-seed"].as<int>() : std::random_device()();
    GeneratorTool generator(DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER>(),  // generator_factory
                            args.count("stdout") ? "" : args["out"].as<std::string>(),  // out_format
                            args.count("rule") ? args["rule"].as<std::string>() : "",  // rule
                            RuleSize(args["max-depth"].as<int>(), args["max-tokens"].as<int>()),  // limit
                            args.count("population") ? new DefaultPopulation(args["population"].as<std::string>(), tree_extension, *tree_codec) : nullptr,  // population
                            !args["no-generate"].as<bool>(),  // generate
                            !args["no-mutate"].as<bool>(),  // mutate
                            !args["no-recombine"].as<bool>(),  // recombine
                            !args["no-grammar-violations"].as<bool>(), // unrestricted
                            args["keep-trees"].as<bool>(),  // keep_trees
                            GRAMMARINATOR_TRANSFORMER ? std::vector<Rule*(*)(Rule*)>{GRAMMARINATOR_TRANSFORMER} : std::vector<Rule*(*)(Rule*)>{},  // transformers
                            GRAMMARINATOR_SERIALIZER,  // serializer
                            args["memo-size"].as<int>(),  // memo-size
                            args["unique-attempts"].as<int>(),  // unique-attempts
                            args["dry-run"].as<bool>(),  // dry-run
                            false  // print_mutators
                            );

    for (int i = 0, n = args["n"].as<int>(); i < n; ++i) {
        random_engine.seed(seed + i);
        generator.create_test(i);
    }

    delete tree_codec;
  } catch (const cxxopts::exceptions::parsing &e) {
    perrf("error parsing options: {}", e.what());
    exit(1);
  }
}
