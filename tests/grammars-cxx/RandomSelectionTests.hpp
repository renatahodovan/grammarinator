// Copyright (c) 2026 Renata Hodovan.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef RANDOM_SELECTION_TESTS_HPP
#define RANDOM_SELECTION_TESTS_HPP

#include <grammarinator/util/random.hpp>

#include <algorithm>
#include <array>
#include <cassert>
#include <map>
#include <vector>

// Check complete permutations and uniform selection from the eligible suffix.
static void test_random_selection() {
  using namespace grammarinator::util;
  random_engine.seed(42);
  std::map<std::vector<int>, int> permutations;
  std::array<int, 2> first_eligible{};
  for (int n = 0; n < 60000; ++n) {
    std::vector<int> values{0, 1, 2};
    int first = -1;
    for (size_t i = 0; i < values.size(); ++i) {
      int value = random_shuffle_next(values, i);
      if (value != 0 && first < 0) first = value;
    }
    ++permutations[values];
    ++first_eligible[first - 1];
    std::sort(values.begin(), values.end());
    assert((values == std::vector<int>{0, 1, 2}));
  }
  assert(permutations.size() == 6);
  for (const auto& [values, count] : permutations) assert(count > 9000 && count < 11000);
  assert(first_eligible[0] > 28500 && first_eligible[0] < 31500);
  std::vector<int> singleton{7};
  assert(random_shuffle_next(singleton, 0) == 7);
}

#endif  // RANDOM_SELECTION_TESTS_HPP
