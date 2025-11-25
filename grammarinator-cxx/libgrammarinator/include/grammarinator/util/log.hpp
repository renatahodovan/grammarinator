// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_UTIL_LOG_HPP
#define GRAMMARINATOR_UTIL_LOG_HPP

#include <format>
#include <iostream>
#include <string>
#include <string_view>

#define GRAMMARINATOR_LOG_LEVEL_OFF   0
#define GRAMMARINATOR_LOG_LEVEL_FATAL 1
#define GRAMMARINATOR_LOG_LEVEL_ERROR 2
#define GRAMMARINATOR_LOG_LEVEL_WARN  3
#define GRAMMARINATOR_LOG_LEVEL_INFO  4
#define GRAMMARINATOR_LOG_LEVEL_DEBUG 5
#define GRAMMARINATOR_LOG_LEVEL_TRACE 6

#ifndef GRAMMARINATOR_LOG_LEVEL
#define GRAMMARINATOR_LOG_LEVEL GRAMMARINATOR_LOG_LEVEL_ERROR
#endif

namespace grammarinator {
namespace util {

template<typename... Args>
void log(std::string_view fmt, Args&&... args) {
  std::string message;
  if constexpr (sizeof...(Args) == 0) {
    message = std::string(fmt);
  } else {
    message = std::vformat(fmt, std::make_format_args(args...));
  }
  std::clog << message << std::endl;
}

}  // namespace util
}  // namespace grammarinator

#if GRAMMARINATOR_LOG_LEVEL >= GRAMMARINATOR_LOG_LEVEL_FATAL
#define GRAMMARINATOR_LOG_FATAL(FMT, ...) ::grammarinator::util::log("\033[95m[F]\033[0m " FMT __VA_OPT__(, ) __VA_ARGS__)
#else
#define GRAMMARINATOR_LOG_FATAL(FMT, ...) do { } while (false)
#endif

#if GRAMMARINATOR_LOG_LEVEL >= GRAMMARINATOR_LOG_LEVEL_ERROR
#define GRAMMARINATOR_LOG_ERROR(FMT, ...) ::grammarinator::util::log("\033[91m[E]\033[0m " FMT __VA_OPT__(, ) __VA_ARGS__)
#else
#define GRAMMARINATOR_LOG_ERROR(FMT, ...) do { } while (false)
#endif

#if GRAMMARINATOR_LOG_LEVEL >= GRAMMARINATOR_LOG_LEVEL_WARN
#define GRAMMARINATOR_LOG_WARN(FMT, ...) ::grammarinator::util::log("\033[93m[W]\033[0m " FMT __VA_OPT__(, ) __VA_ARGS__)
#else
#define GRAMMARINATOR_LOG_WARN(FMT, ...) do { } while (false)
#endif

#if GRAMMARINATOR_LOG_LEVEL >= GRAMMARINATOR_LOG_LEVEL_INFO
#define GRAMMARINATOR_LOG_INFO(FMT, ...) ::grammarinator::util::log("\033[92m[I]\033[0m " FMT __VA_OPT__(, ) __VA_ARGS__)
#else
#define GRAMMARINATOR_LOG_INFO(FMT, ...) do { } while (false)
#endif

#if GRAMMARINATOR_LOG_LEVEL >= GRAMMARINATOR_LOG_LEVEL_DEBUG
#define GRAMMARINATOR_LOG_DEBUG(FMT, ...) ::grammarinator::util::log("\033[94m[D]\033[0m " FMT __VA_OPT__(, ) __VA_ARGS__)
#else
#define GRAMMARINATOR_LOG_DEBUG(FMT, ...) do { } while (false)
#endif

#if GRAMMARINATOR_LOG_LEVEL >= GRAMMARINATOR_LOG_LEVEL_TRACE
#define GRAMMARINATOR_LOG_TRACE(FMT, ...) ::grammarinator::util::log("\033[96m[T]\033[0m " FMT __VA_OPT__(, ) __VA_ARGS__)
#else
#define GRAMMARINATOR_LOG_TRACE(FMT, ...) do { } while (false)
#endif

#endif  // GRAMMARINATOR_UTIL_LOG_HPP
