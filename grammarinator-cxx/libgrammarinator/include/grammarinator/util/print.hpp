// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_UTIL_PRINT_HPP
#define GRAMMARINATOR_UTIL_PRINT_HPP

#include <format>
#include <iostream>
#include <string_view>

namespace grammarinator {
namespace util {

template<typename Arg>
void pout(Arg&& arg) {
  std::cout << arg << std::endl;
}

template<typename... Args>
void poutf(std::string_view fmt, Args&&... args) {
  std::cout << std::vformat(fmt, std::make_format_args(args...)) << std::endl;
}

template<typename Arg>
void perr(Arg&& arg) {
  std::cerr << arg << std::endl;
}

template<typename... Args>
void perrf(std::string_view fmt, Args&&... args) {
  std::cerr << std::vformat(fmt, std::make_format_args(args...)) << std::endl;
}

} // namespace util
} // namespace grammarinator

#endif  // GRAMMARINATOR_UTIL_PRINT_HPP
