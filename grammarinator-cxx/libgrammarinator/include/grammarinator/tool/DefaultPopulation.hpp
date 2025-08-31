// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_DEFAULTPOPULATION_HPP
#define GRAMMARINATOR_TOOL_DEFAULTPOPULATION_HPP

#include "../runtime/Population.hpp"
#include "../util/print.hpp"
#include "FlatBuffersTreeCodec.hpp"
#include "TreeCodec.hpp"

#include <filesystem>
#include <fstream>
#include <glob.h>
#include <string>
#include <vector>

namespace grammarinator {
namespace tool {

class DefaultPopulation;

class DefaultIndividual : public runtime::Individual {
private:
  DefaultPopulation* population_;
  runtime::Rule* root_{};

public:
  DefaultIndividual(DefaultPopulation* population, const std::string& name)
      : Individual(name), population_(population) { }

  DefaultIndividual(const DefaultIndividual& other) = delete;
  DefaultIndividual& operator=(const DefaultIndividual& other) = delete;
  DefaultIndividual(DefaultIndividual&& other) = delete;
  DefaultIndividual& operator=(DefaultIndividual&& other) = delete;

  ~DefaultIndividual() override {
    if (root_) {
      delete root_;
    }
  }

  runtime::Rule* root() override;
};

class DefaultPopulation : public runtime::Population {
private:
  std::string directory_;
  std::string extension_;
  const TreeCodec& codec_;
  std::vector<std::string> files_{};

public:
  DefaultPopulation(const std::string& directory, const std::string& extension,
                    const TreeCodec& codec = FlatBuffersTreeCodec())
      : directory_(directory), extension_(extension), codec_(codec) {
    if (!directory.empty()) {
      try {
        std::filesystem::create_directories(directory);
      } catch (const std::filesystem::filesystem_error& e) {
        util::perrf("Failed to create population directory '{}': {}", directory, e.what());
      }

      glob_t glob_result;
      std::string pattern = directory + "/*." + extension;
      glob(pattern.c_str(), GLOB_TILDE, NULL, &glob_result);

      for (size_t i = 0; i < glob_result.gl_pathc; i++) {
        files_.push_back(glob_result.gl_pathv[i]);
      }

      globfree(&glob_result);
    }
  }

  DefaultPopulation(const DefaultPopulation& other) = delete;
  DefaultPopulation& operator=(const DefaultPopulation& other) = delete;
  DefaultPopulation(DefaultPopulation&& other) = delete;
  DefaultPopulation& operator=(DefaultPopulation&& other) = delete;
  ~DefaultPopulation() override = default;

  bool empty() const override { return files_.size() == 0; }

  void add_individual(runtime::Rule* root, const std::string& path = "") override {
    std::string fn = std::filesystem::path(path).filename();

    if (fn.empty()) {
      fn = "DefaultPopulation";
    }
    fn = std::filesystem::path(directory_) / (fn + "." + extension_);

    save(fn, root);
    files_.push_back(fn);
  }

  DefaultIndividual* select_individual() override {
    return new DefaultIndividual(this, files_[util::random_int<size_t>(0, files_.size() - 1)]);
  }

private:
  void save(const std::string& fn, runtime::Rule* root) {
    std::vector<uint8_t> buffer = codec_.encode(root);

    std::ofstream outfile(fn, std::ios::binary | std::ios::out);
    outfile.write(reinterpret_cast<const char*>(buffer.data()), buffer.size());
    outfile.close();
  }

  runtime::Rule* load(const std::string& fn) {
    std::ifstream infile(fn, std::ios::binary | std::ios::ate);
    if (!infile.is_open()) {
      return nullptr;
    }

    std::streamsize size = infile.tellg();
    infile.seekg(0, std::ios::beg);
    std::vector<uint8_t> buffer;
    buffer.resize(size);

    infile.unsetf(std::ios::skipws); // FIXME: Stop eating new lines in binary mode (necessary?)
    if (!infile.read(reinterpret_cast<char*>(buffer.data()), size)) {
      return nullptr;
    }
    infile.close();

    return codec_.decode(buffer);
  }

  friend class DefaultIndividual;
};

inline runtime::Rule* DefaultIndividual::root() {
  if (!root_) {
    root_ = population_->load(name);
  }
  return root_;
}

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_DEFAULTPOPULATION_HPP
