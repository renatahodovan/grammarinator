# Copyright (c) 2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

cmake_minimum_required(VERSION 3.10)
project(grammarinator-cxx CXX)

option(GRAMMARINATOR_TOOLS "build tool artefacts" OFF)
option(GRAMMARINATOR_GRLF "build libgrlf" OFF)
option(GRAMMARINATOR_FUZZNULL "build fuzznull tool" OFF)

set(GRAMMARINATOR_GENERATOR "" CACHE STRING "name of the generator class created by grammarinator-process (mandatory for specialized artefacts)")
set(GRAMMARINATOR_MODEL "" CACHE STRING "name of the decision model class (for specialized artefacts)")
set(GRAMMARINATOR_LISTENER "" CACHE STRING "name of the listener class (for specialized artefacts)")
set(GRAMMARINATOR_TRANSFORMER "" CACHE STRING "name of the transformer function (for specialized artefacts)")
set(GRAMMARINATOR_SERIALIZER "" CACHE STRING "name of the serializer function (for specialized artefacts)")
set(GRAMMARINATOR_TREECODEC "" CACHE STRING "name of the tree codec class (for specialized artefacts)")
set(GRAMMARINATOR_INCLUDE "" CACHE STRING "path to a header file (relative to the include path) to include during compilation (for specialized artefacts)")
set(GRAMMARINATOR_INCLUDEDIR "" CACHE STRING "path to a directory to add to the include path during compilation (for specialized artefacts)")
set(GRAMMARINATOR_SUFFIX "" CACHE STRING "suffix to append to the names of specialized artefacts")

macro(grammarinator_status VARIABLE)
  message(STATUS "${VARIABLE}: ${${VARIABLE}}")
endmacro()

macro(grammarinator_define TARGET VARIABLE)
  if (NOT ("${${VARIABLE}}" STREQUAL ""))
    target_compile_definitions(${TARGET} PRIVATE "${VARIABLE}=${${VARIABLE}}")
  endif()
endmacro()

macro(grammarinator_spec_target_name TARGET_VARIABLE TARGET_NAME)
  if (NOT ("${GRAMMARINATOR_SUFFIX}" STREQUAL ""))
    set(${TARGET_VARIABLE} "${TARGET_NAME}-${GRAMMARINATOR_SUFFIX}")
  else()
    set(${TARGET_VARIABLE} "${TARGET_NAME}")
  endif()
endmacro()

macro(grammarinator_spec_definitions TARGET)
  grammarinator_define(${TARGET} GRAMMARINATOR_GENERATOR)
  grammarinator_define(${TARGET} GRAMMARINATOR_MODEL)
  grammarinator_define(${TARGET} GRAMMARINATOR_LISTENER)
  grammarinator_define(${TARGET} GRAMMARINATOR_TRANSFORMER)
  grammarinator_define(${TARGET} GRAMMARINATOR_SERIALIZER)
  grammarinator_define(${TARGET} GRAMMARINATOR_TREECODEC)
  grammarinator_define(${TARGET} GRAMMARINATOR_INCLUDE)
  if (NOT ("${GRAMMARINATOR_INCLUDEDIR}" STREQUAL ""))
    target_include_directories(${TARGET} PRIVATE "${GRAMMARINATOR_INCLUDEDIR}")
  endif()
  target_include_directories(${TARGET} PRIVATE "${CMAKE_SOURCE_DIR}/common")
endmacro()

execute_process(COMMAND git describe --tags
                WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
                OUTPUT_VARIABLE GRAMMARINATOR_VERSION
                OUTPUT_STRIP_TRAILING_WHITESPACE)

if(GRAMMARINATOR_FUZZNULL)
  set(GRAMMARINATOR_GRLF ON)
endif()

grammarinator_status(GRAMMARINATOR_VERSION)
grammarinator_status(GRAMMARINATOR_TOOLS)
grammarinator_status(GRAMMARINATOR_GRLF)
grammarinator_status(GRAMMARINATOR_FUZZNULL)

if(GRAMMARINATOR_TOOLS OR GRAMMARINATOR_GRLF OR GRAMMARINATOR_FUZZNULL)
  if ("${GRAMMARINATOR_SUFFIX}" STREQUAL "")
    set(GRAMMARINATOR_SUFFIX "${GRAMMARINATOR_GENERATOR}")
    string(TOLOWER "${GRAMMARINATOR_SUFFIX}" GRAMMARINATOR_SUFFIX)
    string(REGEX REPLACE "^(.*)generator$" "\\1" GRAMMARINATOR_SUFFIX "${GRAMMARINATOR_SUFFIX}")
  endif()

  grammarinator_status(GRAMMARINATOR_GENERATOR)
  grammarinator_status(GRAMMARINATOR_MODEL)
  grammarinator_status(GRAMMARINATOR_LISTENER)
  grammarinator_status(GRAMMARINATOR_TRANSFORMER)
  grammarinator_status(GRAMMARINATOR_SERIALIZER)
  grammarinator_status(GRAMMARINATOR_TREECODEC)
  grammarinator_status(GRAMMARINATOR_INCLUDE)
  grammarinator_status(GRAMMARINATOR_INCLUDEDIR)
  grammarinator_status(GRAMMARINATOR_SUFFIX)
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_definitions(GRAMMARINATOR_VERSION=${GRAMMARINATOR_VERSION})
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wno-error -O3")

# Setup directories
# Note: This mimics a conventional file system layout in the build directory for
# the sake of convenient location of build artefacts. Proper installation to
# traditional locations is also supported, e.g., to /usr/local.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin/")
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib/")
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/lib/")

list(APPEND CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
list(APPEND CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})

add_subdirectory(libgrammarinator)
if(GRAMMARINATOR_GRLF)
  add_subdirectory(libgrlf)
endif()
if(GRAMMARINATOR_TOOLS OR GRAMMARINATOR_FUZZNULL)
  add_subdirectory(tools)
endif()
