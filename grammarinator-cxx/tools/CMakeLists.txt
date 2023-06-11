# Copyright (c) 2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

find_package(cxxopts REQUIRED)

grammarinator_spec_target_name(GENERATE generate)
add_executable(${GENERATE} generate.cpp)
grammarinator_spec_definitions(${GENERATE})
target_link_libraries(${GENERATE} grammarinator cxxopts::cxxopts -std=c++20)

# install(TARGETS ${GENERATE} DESTINATION bin)

grammarinator_spec_target_name(FUZZNULL fuzznull)
add_executable(${FUZZNULL} fuzznull.cpp)
target_compile_options(${FUZZNULL} PRIVATE -fsanitize=fuzzer)
target_link_libraries(${FUZZNULL} ${GRLF} -fsanitize=fuzzer,address -std=c++20)
