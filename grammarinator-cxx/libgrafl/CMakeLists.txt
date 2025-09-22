# Copyright (c) 2025-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

grammarinator_spec_target_name(GRAFL grafl)
add_library(${GRAFL} SHARED grafl.cpp)
if(NOT DEFINED GRAMMARINATOR_AFL_INCLUDEDIR)
  message(FATAL_ERROR "GRAMMARINATOR_AFL_INCLUDEDIR not set.")
endif()
target_include_directories(${GRAFL} PRIVATE ${GRAMMARINATOR_AFL_INCLUDEDIR})
grammarinator_spec_definitions(${GRAFL})
target_link_libraries(${GRAFL} PRIVATE grammarinator)

configure_file(libgrafl.pc.in lib${GRAFL}.pc @ONLY)

install(TARGETS ${GRAFL} DESTINATION lib)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/lib${GRAFL}.pc DESTINATION lib/pkgconfig)

set(GRAFL ${GRAFL} PARENT_SCOPE)
