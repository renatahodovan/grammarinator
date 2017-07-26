=============================
*Grammarinator* Release Notes
=============================

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
