// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_MODEL_HPP
#define GRAMMARINATOR_RUNTIME_MODEL_HPP

#include "Rule.hpp"

#include <string>
#include <vector>

namespace grammarinator {
namespace runtime {

class Generator;

class Model {
public:
  Generator* gen{};  // NOTE: Python version does not have a gen field

  Model() = default;
  Model(const Model& other) = delete;
  Model& operator=(const Model& other) = delete;
  Model(Model&& other) = delete;
  Model& operator=(Model&& other) = delete;
  virtual ~Model() = default;

  virtual int choice(const Rule* node, int idx, const std::vector<double>& weights) = 0;
  virtual bool quantify(const Rule* node, int idx, int cnt, int start, int stop, double prob = 0.5) = 0;
  virtual std::string charset(const Rule* node, int idx, const std::vector<std::string>& chars) = 0;
};

} // namespace runtime
} // namespace grammarinator

#endif // GRAMMARINATOR_RUNTIME_MODEL_HPP
