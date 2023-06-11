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
#warning "GRAMMARINATOR_MODEL is undefined, using grammarinator::runtime::DefaultModel"
#include "grammarinator/runtime/DefaultModel.hpp"
#endif

#ifndef GRAMMARINATOR_LISTENER
#define GRAMMARINATOR_LISTENER grammarinator::runtime::Listener
#warning "GRAMMARINATOR_LISTENER is undefined, using grammarinator::runtime::Listener"
#include "grammarinator/runtime/Listener.hpp"
#endif

#ifndef GRAMMARINATOR_TRANSFORMER
#define GRAMMARINATOR_TRANSFORMER nullptr
#warning "GRAMMARINATOR_TRANSFORMER is undefined, using nullptr"
#endif

#ifndef GRAMMARINATOR_SERIALIZER
#define GRAMMARINATOR_SERIALIZER grammarinator::runtime::SimpleSpaceSerializer
#warning "GRAMMARINATOR_SERIALIZER is undefined, using grammarinator::runtime::SimpleSpaceSerializer"
#include "grammarinator/runtime/Serializer.hpp"
#endif

#ifndef GRAMMARINATOR_TREECODEC
#define GRAMMARINATOR_TREECODEC grammarinator::tool::FlatBuffersTreeCodec
#warning "GRAMMARINATOR_TREECODEC is undefined, using grammarinator::tool::FlatBuffersTreeCodec"
#include "grammarinator/tool/FlatBuffersTreeCodec.hpp"
#endif

#ifndef GRAMMARINATOR_INCLUDE
#define GRAMMARINATOR_INCLUDE GRAMMARINATOR_GENERATOR.hpp
#warning "GRAMMARINATOR_INCLUDE is undefined, using GRAMMARINATOR_GENERATOR.hpp"
#endif
#define GRAMMARINATOR_STRFY_INTERNAL(MACRO) #MACRO
#define GRAMMARINATOR_STRFY(MACRO) GRAMMARINATOR_STRFY_INTERNAL(MACRO)
#include GRAMMARINATOR_STRFY(GRAMMARINATOR_INCLUDE)
