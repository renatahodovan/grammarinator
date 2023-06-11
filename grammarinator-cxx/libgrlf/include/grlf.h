// Copyright (c) 2025 Renata Hodovan, Akos Kiss.
//
// Licensed under the BSD 3-Clause License
// <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
// This file may not be copied, modified, or distributed except
// according to those terms.

#ifndef GRLF_H
#define GRLF_H

// The C API of the Grammarinator-LibFuzzer integration library (GRLF).
// The functions are intended to be used in LibFuzzer targets, i.e., where
// LLVMFuzzerTestOneInput is defined.

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif // __cplusplus

int GrammarinatorInitialize(int* argc, char*** argv);

size_t GrammarinatorGenerator(uint8_t* Data, size_t Size, size_t MaxSize, unsigned int Seed);

size_t GrammarinatorMutator(uint8_t* Data, size_t Size, size_t MaxSize, unsigned int Seed);

size_t GrammarinatorCrossOver(uint8_t* Data1, size_t Size1, const uint8_t* Data2, size_t Size2,
                              uint8_t* Out, size_t MaxOutSize, unsigned int Seed);

void GrammarinatorOneInput(const uint8_t** Data, size_t* Size);

#ifdef __cplusplus
} // extern "C"
#endif // __cplusplus

// When defining GRLF_DEFAULT_INITIALIZATION and/or GRLF_DEFAULT_INTEGRATION or
// GRLF_BLACKBOX_INTEGRATION macros before including grlf.h, implementations for
// some of the LibFuzzer interface functions are defined.
//
// GRLF_DEFAULT_INITIALIZATION triggers the definition of LLVMFuzzerInitialize.
//
// GRLF_DEFAULT_INTEGRATION triggers the definition of LLVMFuzzerCustomMutator
// and LLVMFuzzerCustomCrossOver, and also re-defines LLVMFuzzerTestOneInput.
// (The original LLVMFuzzerTestOneInput is renamed to GrammarinatorTestOneInput
// with the help of the preprocessor.)
//
// GRLF_BLACKBOX_INTEGRATION triggers the definition of LLVMFuzzerCustomMutator.
//
// Note: GRLF_DEFAULT_INTEGRATION and GRLF_BLACKBOX_INTEGRATION are mutually
// exclusive.

#if defined(GRLF_DEFAULT_INTEGRATION) && defined(GRLF_BLACKBOX_INTEGRATION)
#error "GRLF_DEFAULT_INTEGRATION and GRLF_BLACKBOX_INTEGRATION must not be defined simultaneously"
#endif

#ifdef __cplusplus
#define GRLF_EXTERN_C extern "C"
#else
#define GRLF_EXTERN_C
#endif // __cplusplus

#ifdef GRLF_DEFAULT_INITIALIZATION
GRLF_EXTERN_C
int LLVMFuzzerInitialize(int* argc, char*** argv) {
  return GrammarinatorInitialize(argc, argv);
}
#endif // GRLF_DEFAULT_INITIALIZATION

#ifdef GRLF_DEFAULT_INTEGRATION
GRLF_EXTERN_C
size_t LLVMFuzzerCustomMutator(uint8_t* Data, size_t Size, size_t MaxSize, unsigned int Seed) {
  return GrammarinatorMutator(Data, Size, MaxSize, Seed);
}

GRLF_EXTERN_C
size_t LLVMFuzzerCustomCrossOver(uint8_t* Data1, size_t Size1, const uint8_t* Data2, size_t Size2,
                                 uint8_t* Out, size_t MaxOutSize, unsigned int Seed) {
  return GrammarinatorCrossOver(Data1, Size1, Data2, Size2, Out, MaxOutSize, Seed);
}

GRLF_EXTERN_C
int GrammarinatorTestOneInput(const uint8_t *Data, size_t Size);

GRLF_EXTERN_C
int LLVMFuzzerTestOneInput(const uint8_t *Data, size_t Size) {
  GrammarinatorOneInput(&Data, &Size);
  return GrammarinatorTestOneInput(Data, Size);
}

#define LLVMFuzzerTestOneInput GrammarinatorTestOneInput
#endif // GRLF_DEFAULT_INTEGRATION

#ifdef GRLF_BLACKBOX_INTEGRATION
GRLF_EXTERN_C
size_t LLVMFuzzerCustomMutator(uint8_t* Data, size_t Size, size_t MaxSize, unsigned int Seed) {
  return GrammarinatorGenerator(Data, Size, MaxSize, Seed);
}
#endif // GRLF_BLACKBOX_INTEGRATION

#undef GRLF_EXTERN_C

#endif // GRLF_H
