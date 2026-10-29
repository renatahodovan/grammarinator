// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_TOOL_FILEPOPULATION_HPP
#define GRAMMARINATOR_TOOL_FILEPOPULATION_HPP

#include "../runtime/Population.hpp"
#include "../util/log.hpp"
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
  std::filesystem::path name_;

public:
  FileIndividual(FilePopulation* population, const std::filesystem::path& name)
      : Individual(), population_(population), name_(name) { }

  FileIndividual(const FileIndividual& other) = delete;
  FileIndividual& operator=(const FileIndividual& other) = delete;
  FileIndividual(FileIndividual&& other) = delete;
  FileIndividual& operator=(FileIndividual&& other) = delete;
  ~FileIndividual() override = default;

  std::string name() const override { return name_.string(); }

  runtime::Rule* root() override;
};

class FilePopulation : public runtime::Population {
private:
  std::filesystem::path directory_;
  std::string extension_;
  const TreeCodec& codec_;
  std::vector<std::filesystem::path> names_{};

public:
  FilePopulation(const std::string& directory, const std::string& extension,
                 const TreeCodec& codec = FlatBuffersTreeCodec())
      : directory_(directory), extension_(extension), codec_(codec) {
    if (!directory_.empty()) {
      std::error_code ec;
      std::filesystem::create_directories(directory_, ec);
      if (ec) {
        GRAMMARINATOR_LOG_FATAL("Failed to create population directory '{}': {}", directory_.string(), ec.message());
      }

      for (auto const& entry : std::filesystem::directory_iterator(directory_)) {
        if (!entry.is_regular_file()) {
          continue;
        }
        auto const& filename = entry.path().filename();
        if (filename.extension() == "." + extension) {
          names_.push_back(filename.stem());
        }
      }
    }
  }

  FilePopulation(const FilePopulation& other) = delete;
  FilePopulation& operator=(const FilePopulation& other) = delete;
  FilePopulation(FilePopulation&& other) = delete;
  FilePopulation& operator=(FilePopulation&& other) = delete;
  ~FilePopulation() override = default;

  bool empty() const override { return names_.size() == 0; }

  void add_individual(runtime::Rule* root, const std::string& path = "") override {
    auto name = std::filesystem::path(path).filename();
    if (name.empty()) {
      name = "FilePopulation";
    }

    if (save(name, root)) {
      names_.push_back(name);
    }
  }

  FileIndividual* select_individual(runtime::Individual* recipient = nullptr) override {
    return new FileIndividual(this, names_[util::random_int<size_t>(0, names_.size() - 1)]);
  }

private:
  bool save(const std::filesystem::path& name, runtime::Rule* root) {
    std::filesystem::path path{directory_};
    path /= name;
    path += "." + extension_;

    std::vector<uint8_t> buffer = codec_.encode(root);
    if (buffer.empty()) {
      GRAMMARINATOR_LOG_WARN("Failed to encode population file '{}'.", path.string());
      return false;
    }

    std::ofstream outfile(path, std::ios::binary | std::ios::trunc);
    outfile.write(reinterpret_cast<const char*>(buffer.data()), buffer.size());
    outfile.close();
    return true;
  }

  runtime::Rule* load(const std::filesystem::path& name) {
    std::filesystem::path path{directory_};
    path /= name;
    path += "." + extension_;

    std::ifstream infile(path, std::ios::binary | std::ios::ate);
    if (!infile.is_open()) {
      GRAMMARINATOR_LOG_WARN("Failed to open population file '{}'.", path.string());
      return nullptr;
    }

    std::streamsize size = infile.tellg();
    if (size < 0) {
      GRAMMARINATOR_LOG_WARN("Failed to determine population file size '{}'.", path.string());
      return nullptr;
    }
    infile.seekg(0, std::ios::beg);
    std::vector<uint8_t> buffer(size);

    if (size > 0 && !infile.read(reinterpret_cast<char*>(buffer.data()), size)) {
      GRAMMARINATOR_LOG_WARN("Failed to read population file '{}'.", path.string());
      return nullptr;
    }
    infile.close();

    return codec_.decode(buffer);
  }

  friend class FileIndividual;
};

inline runtime::Rule* FileIndividual::root() {
  auto r = Individual::root();
  if (r) {
    return r;
  }
  r = population_->load(name_);
  if (!r) {
    GRAMMARINATOR_LOG_WARN("Failed to load individual from '{}'.", name_.string());
    return nullptr;
  }
  root_->add_child(r);
  return r;
}

} // namespace tool
} // namespace grammarinator

#endif // GRAMMARINATOR_TOOL_FILEPOPULATION_HPP
