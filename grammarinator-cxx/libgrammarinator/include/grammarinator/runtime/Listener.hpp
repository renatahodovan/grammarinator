// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_RUNTIME_LISTENER_HPP
#define GRAMMARINATOR_RUNTIME_LISTENER_HPP

#include "Rule.hpp"

namespace grammarinator {
namespace runtime {

class Listener {
public:
  Listener() = default;
  Listener(const Listener& other) = delete;
  Listener& operator=(const Listener& other) = delete;
  Listener(Listener&& other) = delete;
  Listener& operator=(Listener&& other) = delete;
  virtual ~Listener() = default;

  virtual void enter_rule(Rule* node) {}
  virtual void exit_rule(Rule* node) {}
};

} // namespace runtime
} // namespace grammarinator

#endif // GRAMMARINATOR_RUNTIME_LISTENER_HPP
