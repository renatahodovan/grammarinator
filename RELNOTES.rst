=============================
*Grammarinator* Release Notes
=============================

.. start included documentation

26.1
====

Summary of changes:

* Grammar feature support:

  * Improved handling of inline literals in parser rules by ensuring a
    corresponding lexer rule always exists.
  * Fixed and extended support for arguments, locals, and returns, including
    complex parameter lists and uninitialized values.
  * Added support for typed rule attributes (args, locals, returns), supporting
    both prefix and postfix type notation.
  * Added support for unicode properties and "not set" constructs in lexer and
    "not set" constructs in parser rules.
  * Improved handling of the dot (``.``) wildcard in parser rules to generate
    random tokens instead of single characters.
  * Added support for rule-level named actions.
  * Enabled rule labels with recurring names and removed incorrect naming
    restrictions.
  * Added support for per-rule options.
  * Ignored the artificial EOF rule during generation and parsing.

* Generated fuzzer, runtime API:

  * Introduced token-based size control in addition to depth-based limits.
  * Improved backtracking logic in quantified expression matching during
    ``grammariantor-parse``
  * Unified the presentation of static size data of various language constructs
    in the generated generator.
  * Added detailed decision nodes (alternatives, quantifiers) to generated
    trees to preserve generation semantics.
  * Improved tree node APIs, including formatting (``str``, ``repr``,
    ``debug``), equality comparison, and token sequence access.
  * Added memoization of generated test cases to improve uniqueness.
  * Improved handling and marking of immutable lexer and parser rules.
  * Refined listener notifications to correctly reflect sub-rule execution.
  * Removed deprecated concepts (e.g., cooldown factor).
  * Introduced grammar-violating mutation support (optional,
    runtime-controlled).

* Population, mutation, and recombination:

  * Introduced new mutation operators (swap, insert, replicate quantified,
    unrestricted delete/hoist).
  * Generalized existing mutators to work on quantified nodes as well.
  * Improved determinism and reproducibility of mutation and recombination.
  * Refactored population handling by introducing Individual abstractions.
  * Renamed DefaultPopulation / DefaultIndividual to FilePopulation /
    FileIndividual.
  * Enabled different selection strategies for donor and recipient individuals.
  * Added support for parsing and using seed inputs with syntax errors, with an
    optional strict mode to discard them.

* Tools and CLI:

  * Extended ``grammarinator-parse`` to accept directories and file patterns.
  * Added dry-run mode and infinite generation (``-n inf``) support to
    ``grammarinator-generate``.
  * Added progress bars for bulk processing tools.
  * Added the ``grammarinator-decode`` CLI utility to convert population trees
    back into test sources.
  * Unified CLI argument conventions across tools.
  * Improved diagnostic messages and error handling throughout the toolchain.
  * Added support for reproducible generation and encoding-error handling in
    memoized workflows.

* Tree codecs and serialization:

  * Introduced a tree codec framework supporting JSON, pickle, and FlatBuffers.
  * Added ``Annotation``-aware codecs and unified infinite quantifier
    representation.
  * Improved serializers and tree printing.
  * Enabled equality comparison of trees.

* C++ backend and native integrations:

  * Added full C++ code generation support with a header-only runtime library.
  * Added C-based helper library (libgrlf) for libFuzzer integration.
  * Introduced AFL++ integration with subtree-based populations and trimming.
  * Added memoization support to LibFuzzer and AFL++ integrations and native
    generators.
  * Improved and modularized the C++ build system (CMake, build helper).
  * Added extensive C++ grammar test coverage and CI integration.

* Documentation:

  * Significantly expanded and unified documentation for Python and C++ usage.
  * Added detailed API documentation, user guides, and backend-specific
    examples.
  * Updated README with end-to-end workflows and minimal working examples.
  * Improved docstring quality, consistency, and formatting.

* Packaging, installation, dependencies:

  * Dropped support for Python 3.7, 3.8, and 3.9; added support up to
    Python 3.14.
  * Updated and pinned key dependencies (ANTLR, FlatBuffers, xxHash, PyPy).
  * Improved ReadTheDocs configuration and build reproducibility.
  * Updated GitHub Actions workflows and toolchain versions.
  * Adopted SPDX license identifiers.

* Testing and CI:

  * Greatly expanded test coverage, including C++ grammar tests.
  * Improved determinism and stability of multiprocessing tests.
  * Added mypy-based static type checking.
  * Improved CI resilience (non-fail-fast, expanded matrices).
  * Regenerated example fuzzers and ensured consistency across backends.

* Under-the-hood:

  * Extensive internal refactoring, cleanup, and API consistency improvements.
  * Improved grammar graph construction and node identification.
  * Optimized static data access and reduced runtime overhead.
  * Introduced interning for static grammar structures.
  * Numerous bug fixes, typo fixes, lint cleanups, and internal
    simplifications.

23.7
====

Summary of changes:

* Grammar feature support:

  * Added support for variables not only in actions but in semantic predicates
    as well.
  * Added supported for args, locals and returns in parser rules.
  * Removed support of the ``member`` alias of the ``members`` named action.

* Generated fuzzer, runtime API:

  * Merged Unlexer and Unparser concepts into a single Generator class.
  * Stabilized the order of methods in the generated fuzzer.
  * Simplified the generated code of alternations.
  * Simplified and improved the handling of empty alternatives.
  * Improved the handling of escape and unicode sequences.
  * Ensured escaping literals in simple alternations, too.
  * Prefixed all hard-coded names in generators with an underscore.
  * Introduced context managers to handle recurring tasks in the generated code,
    e.g., to perform depth control and method enter/exit tasks.
  * Adapting the value of max_depth if needed to avoid erroring out during test
    case generation.
  * Moved the decision logic of alternatives, quantifiers, and charsets into
    dedicated Model classes.
  * Introduced CooldownModel class to increase grammar coverage.
  * Added support for Listeners.
  * Renamed BaseRule class to Rule.
  * Added support for alternative Population implementations.

* Tools:

  * Split tool API from CLI.
  * Introduced ProcessorTool class for fuzzer generation, ParserTool class for
    creating a population from existing test cases, and GeneratorTool class for
    test case generation.
  * Removed the support for JSON-string arguments in tool initializers (may
    cause issues with Fuzzinator integration).
  * Unified the format of reference to generators, models, and transformers from
    CLI.
  * Added support for handling encoding errors.
  * Added support for reproducible test generation.
  * Added CLI option to generator-process to set/override grammar-level options.
  * Enabled grammarinator-generate to generate tests infinitely.
  * Changed the default naming pattern of output files to contain their indices.
  * Added support to generate a whole batch of tests into the same file (with
    rewriting it over and over).
  * Added support to write the generated output to the standard output.
  * Merged tree and test transformers into a single general transformer concept.
  * Added grammar analyzer functionality to grammarinator-process.
  * Raising error in case of rule redefinition.
  * Giving feedback about the result of tree saving.

* Packaging, installation, dependencies:

  * Moved to pyproject.toml & setup.cfg-based packaging.
  * Added classification metadata to project.
  * Made use of setuptools_scm in versioning.
  * Increased the minimum required Python version from 3.5 to 3.7.
  * Upgraded ANTLRv4 runtime and jar to version 4.13.0.
  * Upgraded ANTLRv4 grammar to the latest official master.
  * Made use of the inators and antlerinator (epoch 1) packages.

* Documentation:

  * Added detailed API Documentation and User Guide.
  * Improved README.

* Testing:

  * Significantly increased the test coverage.
  * Better control of multiprocessing in unit tests.
  * Ensured correct tree structure in tests and examples by using ``replace``.
  * Fixed flakyness in test caused by division by zero.
  * Migrated CI testing from AppVeyor and Travis CI to GitHub Actions.
  * Improved testing on GH Actions (testing Python 3.9, 3.10, 3.11 and PyPy 3.9)
  * Added tox environment to automatically regenerate the example HTML fuzzer.

* Under-the-hood:

  * Switched to jinja template-based fuzzer generation.
  * Moved the generation of ANTLRv4Lexer and ANTLRv4Parser modules to build-time
    to avoid repeatedly regenerating them.
  * Removed the superfluous ANTLRv4JavaLexer.g4 and LexerAdaptor.java files
    since Java target is not supported (yet?).
  * Heavily reworked the graph building part of grammarinator-process.
  * Reworked the processing of charsets.
  * Generalized quantifier handling.
  * Improved the internal representation and calculation of min depths.
  * Improved the tree printing methods of various tree representations (parse
    tree and generated tree).
  * Moved the handling of common CLI arguments into a separate module.
  * Refactored the CLI of process, parse, and generate.
  * Avoided the initialization of a default logging handler when used as a
    module.
  * Several additional pylint, typo, and functional bug fixes, internal
    refactorings, renamings, cleanups.


19.3
====

Summary of changes:

* Added support for parallel test case generation.
* Added support for custom fuzzer superclasses.
* Upgraded dependency to *ANTLeRinator* 4.7.1-1.
* Improved the generation of "dot" (i.e., "any character").
* Improved diagnostic messages.
* Improved the testing infrastructure (maintenance changes to various CI
  configurations).
* Bug fixes (variables in labeled alternatives, node selection of evolutionary
  operators).


18.10
=====

Summary of changes:

* Added support for parsing existing test cases and applying evolutionary
  operators to them (e.g., to mutate and recombine them).
* Added support for a cool-down mechanism to deprioritize already taken
  alternatives during generation, thus giving others a higher probability and
  helping to reach all parts of the grammar.
* Added support for labelled alternatives in grammars to ease the navigation in
  the tree representation of the generated test case.
* Upgraded dependency to ANTLR v4.7.1 (via *ANTLeRinator*).
* Improved the testing infrastructure (simplified and unified config files,
  followed up on pep8 tool name change, added support for Python 3.7).
* Minor bug fixes and improvements.


17.7
====

Summary of changes:

* Added support for controlling recursion depth during test case generation.
* Added support for alternative import grammar directory.
* Added support for default start rule for test case generation.
* Added testing infrastructure (pytest-driven testing and coverage measurement;
  pylint and pep8-based linting; tox for environment management; Travis CI,
  AppVeyor, and Coveralls as online services).
* Improved README to help with first steps with *Grammarinator*.
* Smaller tool improvements (configurable grammar and test case encoding, better
  CLI messages, internal code refactorings).
* Improvements and bug fixes to ANTLR v4 grammar format compatibility (token
  reference negation, EOF token handling, charset references, dashes in
  character classes, lexer modes, empty alternatives, curly braces in inline
  code or literals, imaginary tokens).


17.5
====

First public release of the *Grammarinator* grammar-based random test generator.

Summary of main features:

* ANTLR v4 grammar format compatibility.
* Command line tool to turn grammars into Python 3 random test generator modules
  (so-called unlexers and unparsers, or fuzzers).
* Out-of-the-box useful command line tool to exercise unparsers and unlexers to
  generate random test cases.
* Customization possibilities via inline code in grammars, post-processing
  transformation steps on unparser/unlexer results, and subclassing of fuzzers.
