// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRAMMARINATOR_VERSION
#define GRAMMARINATOR_VERSION "0.0 (unknown)"
#endif

#ifndef GRAMMARINATOR_GENERATOR
#error "GRAMMARINATOR_GENERATOR must be defined"
#endif

#ifndef GRAMMARINATOR_MODEL
#define GRAMMARINATOR_MODEL grammarinator::runtime::DefaultModel
#endif

#ifndef GRAMMARINATOR_LISTENER
#define GRAMMARINATOR_LISTENER grammarinator::runtime::Listener
#endif

#ifndef GRAMMARINATOR_TRANSFORMER
#define GRAMMARINATOR_TRANSFORMER nullptr
#endif

#ifndef GRAMMARINATOR_SERIALIZER
#define GRAMMARINATOR_SERIALIZER grammarinator::runtime::SimpleSpaceSerializer
#endif

#ifndef GRAMMARINATOR_TREECODEC
#define GRAMMARINATOR_TREECODEC grammarinator::tool::FlatBuffersTreeCodec
#endif

#ifndef GRAMMARINATOR_INCLUDE
#define GRAMMARINATOR_INCLUDE GRAMMARINATOR_GENERATOR.hpp
#endif

#define GRAMMARINATOR_STRFY_INTERNAL(MACRO) #MACRO
#define GRAMMARINATOR_STRFY(MACRO) GRAMMARINATOR_STRFY_INTERNAL(MACRO)
#include GRAMMARINATOR_STRFY(GRAMMARINATOR_INCLUDE)
