// Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_UTIL_RANDOM_HPP
#define GRAMMARINATOR_UTIL_RANDOM_HPP

#include <random>
#include <utility>
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

// Swap a randomly chosen element of values[index..] to values[index] and
// return it. Calling this with index = 0, 1, 2, ... visits the elements in a
// random order, like std::shuffle followed by a loop would, but only shuffles
// as many elements as are actually visited.
template<class T>
T& random_shuffle_next(std::vector<T>& values, size_t index) {
  if (index + 1 < values.size()) {
    std::swap(values[index], values[random_int<size_t>(index, values.size() - 1)]);
  }
  return values[index];
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
