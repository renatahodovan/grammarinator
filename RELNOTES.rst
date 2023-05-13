=============================
*Grammarinator* Release Notes
=============================

.. start included documentation

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
