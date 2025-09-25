# Copyright (c) 2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

find_package(flatbuffers REQUIRED)
find_package(nlohmann_json REQUIRED)
find_package(xxHash REQUIRED)

add_library(flatbuffers_headers INTERFACE)
target_include_directories(flatbuffers_headers INTERFACE ${flatbuffers_INCLUDE_DIRS})

add_library(xxhash_headers INTERFACE)
target_include_directories(xxhash_headers INTERFACE ${xxHash_INCLUDE_DIRS})
target_compile_definitions(xxhash_headers INTERFACE XXH_INLINE_ALL)

build_flatbuffers(${CMAKE_SOURCE_DIR}/../grammarinator/tool/resources/fbs/FBRule.fbs
                  ""
                  grammarinator_tool_fbs
                  ""
                  "${CMAKE_CURRENT_BINARY_DIR}/generated_include/grammarinator/tool/fbs"
                  ""
                  "")

add_library(grammarinator INTERFACE)
target_include_directories(grammarinator INTERFACE
                           ${CMAKE_CURRENT_SOURCE_DIR}/include
                           ${CMAKE_CURRENT_BINARY_DIR}/generated_include)
target_link_libraries(grammarinator INTERFACE flatbuffers_headers nlohmann_json::nlohmann_json xxhash_headers)
add_dependencies(grammarinator grammarinator_tool_fbs)

configure_file(libgrammarinator.pc.in libgrammarinator.pc @ONLY)

install(TARGETS grammarinator DESTINATION lib)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/libgrammarinator.pc DESTINATION lib/pkgconfig)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/include/ DESTINATION include)
install(DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/generated_include/ DESTINATION include)
