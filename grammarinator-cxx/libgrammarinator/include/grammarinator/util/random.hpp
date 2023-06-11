// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_UTIL_RANDOM_HPP
#define GRAMMARINATOR_UTIL_RANDOM_HPP

#include <random>
#include <vector>

namespace grammarinator {
namespace util {

inline std::default_random_engine random_engine;

template<class RealType = double>
RealType random_real(RealType a, RealType b) {
  std::uniform_real_distribution<RealType> dist(a, b);
  return dist(random_engine);
}

template<class IntType = int>
IntType random_int(IntType a, IntType b) {
  std::uniform_int_distribution<IntType> dist(a, b);
  return dist(random_engine);
}

inline bool random_bool() {
  std::uniform_int_distribution<int> dist(0, 1);
  return dist(random_engine) == 1;
}

inline int random_weighted_choice(const std::vector<double>& weights) {
  std::discrete_distribution<> dist(weights.begin(), weights.end());
  return dist(random_engine);
}

} // namespace util
} // namespace grammarinator

#endif // GRAMMARINATOR_UTIL_RANDOM_HPP
