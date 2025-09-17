# Copyright (c) 2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

grammarinator_spec_target_name(GRLF grlf)
add_library(${GRLF} STATIC grlf.cpp)
target_include_directories(${GRLF} PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)
grammarinator_spec_definitions(${GRLF})
target_link_libraries(${GRLF} PRIVATE grammarinator)

configure_file(libgrlf.pc.in lib${GRLF}.pc @ONLY)

install(TARGETS ${GRLF} DESTINATION lib)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/lib${GRLF}.pc DESTINATION lib/pkgconfig)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/include/ DESTINATION include)

set(GRLF ${GRLF} PARENT_SCOPE)
