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

#ifndef GRAMMARINATOR_GENERATOR
#error "GRAMMARINATOR_GENERATOR must be defined"
#endif

using namespace grammarinator::runtime;
using namespace grammarinator::tool;
using namespace grammarinator::util;

template<class T>
TreeCodec* treecodec_factory() { return new T(); }

static const std::map<std::string, std::tuple<std::string, TreeCodec*(*)()>> tree_formats = {
  {"flatbuffers", {"grtf", treecodec_factory<FlatBuffersTreeCodec>}},
  {"json", {"grtj", treecodec_factory<JsonTreeCodec>}},
};

// Trim from both ends (in place)
inline void trim(std::string& s) {
    auto not_space = std::not_fn(static_cast<int(*)(int)>(std::isspace));

    s.erase(s.begin(), std::find_if(s.begin(), s.end(), not_space));
    s.erase(std::find_if(s.rbegin(), s.rend(), not_space).base(), s.end());
}

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
      ("weights",
       "JSON file defining custom weights for alternatives",
       cxxopts::value<std::string>(),
       "FILE")
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
      ("allowlist",
       "list of enabled test creators",
       cxxopts::value<std::vector<std::string>>())
      ("blocklist",
       "list of disabled test creators",
       cxxopts::value<std::vector<std::string>>())
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

    // Parse optional custom weights from JSON
    runtime::WeightedModel::WeightMap weights;
    if (args.count("weights")) {
      JsonWeightLoader().load(args["weights"].as<std::string>(), weights);
    }

    auto allowlist = args.count("allowlist")
        ? args["allowlist"].as<std::vector<std::string>>()
        : std::vector<std::string>{};
    for (auto& s : allowlist) {
      trim(s);
    }

    auto blocklist = args.count("blocklist")
        ? args["blocklist"].as<std::vector<std::string>>()
        : std::vector<std::string>{};
    for (auto& s : blocklist) {
      trim(s);
    }

    FilePopulation *population = args.count("population") ? new FilePopulation(args["population"].as<std::string>(), tree_extension, *tree_codec) : nullptr;
    int seed = args.count("random-seed") ? args["random-seed"].as<int>() : std::random_device()();
    GeneratorTool generator(DefaultGeneratorFactory<GRAMMARINATOR_GENERATOR, GRAMMARINATOR_MODEL, GRAMMARINATOR_LISTENER>(weights),  // generator_factory
                            args.count("stdout") ? "" : args["out"].as<std::string>(),  // out_format
                            args.count("rule") ? args["rule"].as<std::string>() : "",  // rule
                            RuleSize(args["max-depth"].as<int>(), args["max-tokens"].as<int>()),  // limit
                            population,  // population
                            args["keep-trees"].as<bool>(),  // keep_trees
                            !args["no-generate"].as<bool>(),  // generate
                            !args["no-mutate"].as<bool>(),  // mutate
                            !args["no-recombine"].as<bool>(),  // recombine
                            !args["no-grammar-violations"].as<bool>(), // unrestricted
                            std::unordered_set<std::string>(allowlist.begin(), allowlist.end()), // allowlist
                            std::unordered_set<std::string>(blocklist.begin(), blocklist.end()), // blocklist
                            GRAMMARINATOR_TRANSFORMER ? std::vector<Rule*(*)(Rule*)>{GRAMMARINATOR_TRANSFORMER} : std::vector<Rule*(*)(Rule*)>{},  // transformers
                            GRAMMARINATOR_SERIALIZER,  // serializer
                            args["memo-size"].as<int>(),  // memo-size
                            args["unique-attempts"].as<int>(),  // unique-attempts
                            args["dry-run"].as<bool>()  // dry-run
                            );

    for (int i = 0, n = args["n"].as<int>(); i < n; ++i) {
        random_engine.seed(seed + i);
        generator.create_test(i);
    }

    delete tree_codec;
    delete population;
  } catch (const cxxopts::exceptions::parsing &e) {
    perrf("error parsing options: {}", e.what());
    exit(1);
  }
}
