.. _aflpp integration:

=================
AFL++ Integration
=================

The C++ backend of *Grammarinator* provides seamless integration with
AFL++ via its custom mutator interface. This allows *Grammarinator*
to be used not only as a blackbox test case generator, but also as an
**in-process input synthesizer**, where its internal derivation trees are
evolved and mutated during fuzzing runs. The mutator operates on serialized
``.grt*`` trees and performs grammar-aware transformations based on the compiled
ANTLR grammar.

Overview
--------

The integration uses the AFL++ custom mutator API `custom mutator hooks`_.
AFL++ loads a shared library implementing these hooks and delegates mutation
and related workflow operations to Grammarinator.

This enables grammar-aware, structure-preserving mutation and recombination
of test cases at runtime -- improving coverage and syntactic correctness
compared to purely byte-level fuzzing.

.. _`custom mutator hooks`: https://github.com/AFLplusplus/AFLplusplus/blob/stable/docs/custom_mutators.md

Building the AFL++-Compatible Mutator
-------------------------------------

To enable this integration in a real AFL++ fuzzing setup, a specialized
shared library must be generated from the C++ generator class produced by
:ref:`grammarinator-process<grammarinator-process>`. This can be compiled
by the :ref:`the build script<cpp_compilation>` using the ``--grafl`` flag
(short for *grammarinator-afl*).

Example using the `HTML grammar`_::

    python3 grammarinator-cxx/dev/build.py --clean \
        --generator HTMLGenerator \
        --includedir <dir-to-HTMLGenerator> \
        --afl-includedir <AFLplusplus-root>/include \
        --serializer SimpleSpaceSerializer \
        --grafl

This command produces a shared library::

    grammarinator-cxx/build/lib/libgrafl-html.so

AFL++ will load this ``.so`` as the custom mutator library through the
``AFL_CUSTOM_MUTATOR_LIBRARY`` environment variable.

Test inputs are expected to be encoded as ``.grt*`` trees
(e.g., FlatBuffer-encoded). During fuzzing, mutations will occur in a
**grammar-aware** manner, resulting in:

- higher syntactic validity of inputs,
- better exploration of the structured input space,
- and potentially deeper semantic bugs found in the target.

Note that only ``.grt*``-style inputs (e.g., ``.grtf`` for FlatBuffer-encoded
trees) are supported by the AFL++ integration.

Fuzzing Configuration
---------------------

Unlike the :ref:`grammarinator-generate<grammarinator-generate>` utility, the
AFL++ custom mutator integration cannot be configured through command-line
arguments. Instead, the behavior of the mutator can be controlled via
environment variables prefixed with ``GRAFL_``.

The following options are currently supported:

* **GRAFL_MAX_DEPTH**: Equivalent to ``--max-depth`` (integer)
* **GRAFL_MAX_TOKENS**: Equivalent to ``--max-tokens`` (integer)
* **GRAFL_MEMO_SIZE**: Equivalent to ``--memo-size`` (integer)
* **GRAFL_RANDOM_MUTATORS**: Enables random mutators;  inverse of
  ``--disable-random-mutators`` (boolean; accepts ``1``, ``true``, or ``yes``
  case-insensitively)
* **GRAFL_WEIGHTS**: Equivalent to ``--weights`` (path to a JSON file)
* **GRAFL_MAX_TRIM_STEPS**: Maximum number of mutation steps performed during
  trimming of a single test input (integer)

Verifying the Setup
-------------------

To run a fuzzing session with AFL++ equipped with Grammarinator, a compiler
wrapper (e.g., ``afl-clang-fast``) and the ``afl-fuzz`` utility must first be
obtained. Both can be installed or built with following the instruction in the
official `AFL++ documentation`_.

Once the target application is compiled with the AFL++ compiler wrapper, the
required instrumentation is automatically injected into the binary. This
instrumentation is later used by ``afl-fuzz`` to guide the fuzzing process.

Next, select or create a grammar that describes the expected input format (e.g.,
`HTML grammar`_), then :ref:`build<cpp_compilation>` the required binaries with
``--grafl``, and optionally also with ``--generate`` and ``--decode`` flags.

The next step is to prepare an initial tree corpus that serves as the starting
point for the fuzzing session. One option is to generate this corpus from
scratch using the :ref:`grammarinator-generate<grammarinator-generate>`
utility. For example::

    grammarinator-generate-html \
        -n 100 \
        -o html-src/%d.html \
        --population html-trees/ \
        --keep-trees

Alternatively, an initial tree corpus can be created by converting existing
source files (e.g., HTML documents) into tree format using the
:ref:`grammarinator-parse<grammarinator-parse>` utility. For example::

    grammarinator-parse html-src \
        -o html-trees \
        -g HTMLLexer.g4 HTMLParser.g4 \
        --tree-format flatbuffers

To test the integration, run AFL++ in custom-mutator-only mode and point it to
the generated shared library::

    AFL_CUSTOM_MUTATOR_ONLY=1 \
    AFL_CUSTOM_MUTATOR_LIBRARY=grammarinator-cxx/build/lib/libgrafl-html.so \
    afl-fuzz -i html-trees -o outdir -- ./target_app @@

Setting ``AFL_CUSTOM_MUTATOR_ONLY=1`` is **mandatory**. Without this flag,
AFL++ would apply its built-in byte-level mutators to the test cases, which
would corrupt the encoded tree representation used by Grammarinator.

**Note 1:** When using AFL++ with Grammarinator integration, both the input
and output corpora must be in tree format. Therefore, any existing input corpus
must first be converted into trees using the
:ref:`grammarinator-parse<grammarinator-parse>` utility. After the fuzzing
session, the resulting tree corpus can be converted back into source-level test
cases using the :ref:`grammarinator-decode<grammarinator-decode-cpp>` utility.

**Note 2:** The items of a tree corpus can be minimized using the ``afl-tmin``
tool in a grammar-aware manner by providing the appropriate custom
mutator-related environment variables. For example::

    AFL_CUSTOM_MUTATOR_ONLY=1 \
    AFL_CUSTOM_MUTATOR_LIBRARY=grammarinator-cxx/build/lib/libgrafl-html.so \
    afl-tmin -i html-trees -o html-trimmed -e -- ./target_app @@

.. _AFL++ documentation: https://aflplus.plus/docs/install/
.. _`HTML grammar`: https://github.com/antlr/grammars-v4/tree/master/html
