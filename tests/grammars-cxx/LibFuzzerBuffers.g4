/*
 * Copyright (c) 2026 Renata Hodovan.
 *
 * Licensed under the BSD 3-Clause License
 * <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
 * This file may not be copied, modified, or distributed except
 * according to those terms.
 */

// TEST-PROCESS-CXX: {grammar}.g4 -o {tmpdir}
// TEST-BUILD-CXX: --generator={grammar}Generator --includedir={tmpdir} --builddir={tmpdir}/build
// TEST-GENERATE-CXX: {tmpdir}/build/bin/grammarinator-generate-{grammar_lower} -r check -n 1 -o {tmpdir}/{grammar}%d.txt

grammar LibFuzzerBuffers;

@header {
#include "LibFuzzerBuffersTests.hpp"
}

check: {test_libfuzzer_buffers<LibFuzzerBuffersGenerator>();} 'ok';
start: TOKEN;
TOKEN: 'a';
