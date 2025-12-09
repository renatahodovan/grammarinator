// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#include <grammarinator/runtime.hpp>
#include <grammarinator/tool.hpp>
#include <grammarinator/util/print.hpp>

#include <cxxopts.hpp>

#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <string>
#include <tuple>
#include <vector>

#include "grammarinator/config.hpp"

using namespace grammarinator::runtime;
using namespace grammarinator::tool;
using namespace grammarinator::util;
namespace fs = std::filesystem;

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
    cxxopts::Options options(argv[0], "Grammarinator: Decode (with C++)");
    options.add_options()
      ("input",
       "input files to process",
       cxxopts::value<std::vector<std::string>>(),
       "PATH")
      ("o,out",
       "directory to save the test cases",
       cxxopts::value<std::string>()->default_value((fs::current_path()).string()),
       "DIR")
      ("stdout",
       "print test cases to stdout (alias for --out='')",
       cxxopts::value<bool>())
      ("tree-format",
       "format of the saved trees (choices: " + tree_format_choices + ")",
       cxxopts::value<std::string>()->default_value("flatbuffers"),
       "NAME")
      ("version", "print version and exit")
      ("help", "print help and exit");

    options.parse_positional({"input"});
    auto args = options.parse(argc, argv);

    if (args.count("help")) {
      pout(options.help());
      exit(0);
    }

    if (args.count("version")) {
      poutf("{} {}", argv[0], GRAMMARINATOR_STRFY(GRAMMARINATOR_VERSION));
      poutf("serializer: {}", GRAMMARINATOR_STRFY(GRAMMARINATOR_SERIALIZER));
      exit(0);
    }

    fs::path out_dir = args.count("stdout") ? "" : args["out"].as<std::string>();
    if (!out_dir.empty()) {
      fs::create_directories(out_dir);
    }

    auto tf_it = tree_formats.find(args["tree-format"].as<std::string>());
    if (tf_it == tree_formats.end()) {
      throw cxxopts::exceptions::parsing("Invalid argument for option 'tree-format'");
    }

    TreeCodec *tree_codec = std::get<1>(tf_it->second)();
    for (const auto &path_str : args["input"].as<std::vector<std::string>>()) {
      // 1) read entire input file into a byte vector
      fs::path in_file{path_str};
      std::ifstream ifs(in_file, std::ios::binary);
      if (!ifs) {
        perrf("Failed to open input file {}.", in_file.string());
        continue;
      }
      std::vector<uint8_t> buffer((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());

      // 2) decode to a Rule* using the selected TreeCodec
      Rule *root = tree_codec->decode(buffer);
      if (!root) {
        perrf("File {} does not contain a valid tree.", in_file.string());
        continue;
      }

      // 3) serialize the decoded tree using the build-time serializer define
      std::string test_src = GRAMMARINATOR_SERIALIZER(root);
      if (!out_dir.empty()) {
        fs::path out_file = out_dir / in_file.stem();
        std::ofstream ofs(out_file);
        ofs << test_src;
        ofs.close();
      } else {
        pout(test_src);
      }
    }

    delete tree_codec;
  } catch (const cxxopts::exceptions::parsing &e) {
    perrf("error parsing options: {}", e.what());
    exit(1);
  }
}
