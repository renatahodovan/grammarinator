// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_FILEPOPULATION_HPP
#define GRAMMARINATOR_TOOL_FILEPOPULATION_HPP

#include "../runtime/Population.hpp"
#include "../util/print.hpp"
#include "FlatBuffersTreeCodec.hpp"
#include "TreeCodec.hpp"

#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
#include <vector>

namespace grammarinator {
namespace tool {

class FilePopulation;

class FileIndividual : public runtime::Individual {
private:
  FilePopulation* population_;
  runtime::Rule* root_{};

public:
  FileIndividual(FilePopulation* population, const std::string& name)
      : Individual(name), population_(population) { }

  FileIndividual(const FileIndividual& other) = delete;
  FileIndividual& operator=(const FileIndividual& other) = delete;
  FileIndividual(FileIndividual&& other) = delete;
  FileIndividual& operator=(FileIndividual&& other) = delete;

  ~FileIndividual() override {
    delete root_;
  }

  runtime::Rule* root() override;
};

class FilePopulation : public runtime::Population {
private:
  std::string directory_;
  std::string extension_;
  const TreeCodec& codec_;
  std::vector<std::string> files_{};

public:
  FilePopulation(const std::string& directory, const std::string& extension,
                 const TreeCodec& codec = FlatBuffersTreeCodec())
      : directory_(directory), extension_(extension), codec_(codec) {
    if (!directory.empty()) {
      std::filesystem::path dirpath(directory);
      std::error_code ec;
      std::filesystem::create_directories(dirpath, ec);
      if (ec) {
        util::perrf("Failed to create population directory '{}': {}", directory, ec.message());
      }

      for (auto const& entry : std::filesystem::directory_iterator(dirpath)) {
        auto const& entrypath = entry.path();
        if (entrypath.extension().string() == "." + extension) {
          files_.push_back(entrypath.string());
        }
      }
    }
  }

  FilePopulation(const FilePopulation& other) = delete;
  FilePopulation& operator=(const FilePopulation& other) = delete;
  FilePopulation(FilePopulation&& other) = delete;
  FilePopulation& operator=(FilePopulation&& other) = delete;
  ~FilePopulation() override = default;

  bool empty() const override { return files_.size() == 0; }

  void add_individual(runtime::Rule* root, const std::string& path = "") override {
    std::string fn = std::filesystem::path(path).filename().string();

    if (fn.empty()) {
      fn = "FilePopulation";
    }
    fn = (std::filesystem::path(directory_) / (fn + "." + extension_)).string();

    save(fn, root);
    files_.push_back(fn);
  }

  FileIndividual* select_individual(runtime::Individual* recipient = nullptr) override {
    return new FileIndividual(this, files_[util::random_int<size_t>(0, files_.size() - 1)]);
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

  friend class FileIndividual;
};

inline runtime::Rule* FileIndividual::root() {
  if (!root_) {
    root_ = population_->load(name);
  }
  return root_;
}

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_FILEPOPULATION_HPP
