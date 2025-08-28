.. _libfuzzer integration:

=====================
LibFuzzer Integration
=====================

The C++ backend of *Grammarinator* provides seamless integration with
libFuzzer via a custom mutator interface. This allows *Grammarinator*
to be used not only as a blackbox test case generator, but also as an
**in-process input synthesizer**, where its internal derivation trees are
evolved and mutated during fuzzing runs. The mutator operates on serialized
``.grt*`` trees and performs grammar-aware transformations based on the compiled
ANTLR grammar.

Overview
--------

The integration supports the ``LLVMFuzzerCustomMutator`` and
``LLVMFuzzerCustomCrossOver`` `libFuzzer hooks`_. These override the default
libFuzzer mutation logic with tree-based logic derived from the grammar.

This enables grammar-aware, structure-preserving mutation and recombination
of test cases at runtime -- improving coverage and syntactic correctness
compared to purely byte-level fuzzing.

.. _`libFuzzer hooks`: https://github.com/google/fuzzing/blob/master/docs/structure-aware-fuzzing.md

Building the libFuzzer-Compatible Mutator
-------------------------------------------

To enable this integration in a real libFuzzer-based fuzzing binary, a
specialized static library must be generated. This is done using the ``--grlf``
flag (short for *grammarinator-libfuzzer*) in the ``build.py`` utility script.

Example using the HTML grammar::

   python3 grammarinator-cxx/dev/build.py --clean \
     --generator HTMLGenerator \
     --includedir examples/fuzzer/ \
     --grlf

This command produces a static library::

   grammarinator-cxx/build/Release/lib/libgrlf-html.a

This ``.a`` file can be linked into a standard libFuzzer fuzz target::

   clang++ <fuzz_target.cpp> -fsanitize=fuzzer grammarinator-cxx/build/Release/lib/libgrlf-html.a

After linking, Grammarinator will handle all mutation logic via its custom
mutator. Test inputs are expected to be serialized ``.grt*`` trees
(e.g., FlatBuffer-encoded). During fuzzing, mutations will occur in a
**grammar-aware** manner, resulting in:

- higher syntactic validity of inputs,
- better exploration of the structured input space,
- and potentially deeper semantic bugs found in the target.

Note that only ``.grt*``-style inputs (e.g., ``.grtf`` for FlatBuffer-encoded
trees) are supported by the libFuzzer integration.

Verifying the Setup
-------------------

If you want to test the integration without a real target, you can build a
dummy binary by adding ``--fuzznull``::

   CXX=clang++ python3 grammarinator-cxx/dev/build.py --clean \
     --generator HTMLGenerator \
     --includedir examples/fuzzer/ \
     --fuzznull

This will create a ``fuzznull-html`` binary under
``grammarinator-cxx/build/Release/bin/``, which can be invoked directly to
verify the setup and test input processing.

Note: clang++ must be used in this case, since other compilers don't support
libFuzzer.
