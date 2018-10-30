=============
Grammarinator
=============
*ANTLRv4 grammar-based test generator*

.. image:: https://badge.fury.io/py/grammarinator.svg
   :target: https://badge.fury.io/py/grammarinator
.. image:: https://travis-ci.org/renatahodovan/grammarinator.svg?branch=master
   :target: https://travis-ci.org/renatahodovan/grammarinator
.. image:: https://ci.appveyor.com/api/projects/status/0f1vm5x9j9j31hpo/branch/master?svg=true
   :target: https://ci.appveyor.com/project/renatahodovan/grammarinator/branch/master
.. image:: https://coveralls.io/repos/github/renatahodovan/grammarinator/badge.svg
   :target: https://coveralls.io/github/renatahodovan/grammarinator

*Grammarinator* is a random test generator / fuzzer that creates test cases
according to an input ANTLR_ v4 grammar. The motivation behind this
grammar-based approach is to leverage the large variety of publicly
available `ANTLR v4 grammars`_.

.. _`ANTLR v4 grammars`: https://github.com/antlr/grammars-v4


Requirements
============

* Python_ >= 3.4
* pip_ and setuptools Python packages (the latter is automatically installed by
  pip).
* ANTLR_ v4

.. _Python: https://www.python.org
.. _pip: https://pip.pypa.io
.. _ANTLR: http://www.antlr.org


Install
=======

The quick way::

    pip3 install grammarinator

Or clone the project and run setuptools::

    python3 setup.py install


Usage
=====

As a first step, *grammarinator* takes an `ANTLR v4`_ grammar and creates a test
generator script in Python3. Such a generator can be subclassed later to
customize it further if needed.

Example usage to create a test generator::

    grammarinator-process <grammar-file(s)> -o <output-directory> --no-actions

.. _`ANTLR v4`: https://github.com/antlr/grammars-v4

**Notes**

Grammarinator uses the `ANTLR v4`_ grammar format as its input, which makes
existing grammars (lexer and parser rules) easily reusable. However, because
of the inherently different goals of a fuzzer and a parser, inlined code
(actions and conditions, header and member blocks) are most probably not
reusable, or even preventing proper execution. For first experiments with
existing grammar files, ``grammarinator-process`` supports the command-line
option ``--no-actions``, which skips all such code blocks during fuzzer
generation. Once inlined code is tuned for fuzzing, that option may be omitted.

After having generated and optionally customized a fuzzer, it can be executed
either by the ``grammarinator-generate`` script or by instantiating it
manually.

Example usage of ``grammarinator-generate``::

    grammarinator-generate -l <unlexer> -p <unparser> -r <start-rule> -d <max-depth> \
    -o <output-pattern> -n <number-of-tests> \
    -t <one-or-more-transformer>

**Notes**

Real-life grammars often use recursive rules to express certain patterns.
However, when using such rule(s) for generation, we can easily end up in an
unexpectedly deep call stack. With the ``--max-depth`` or ``-d`` options, this
depth - and also the size of the generated test cases - can be controlled.

Another speciality of the ANTLR grammars is that they support the so-called
hidden tokens. These rules typically describe such elements of the target
language that can be placed basically anywhere without breaking the syntax. The
most common examples are comments or whitespaces. However, when using these
grammars - which don't define explicitly where whitespace may or may not appear
in rules - to generate test cases, we have to insert the missing spaces
manually. This can be done by applying various transformers (with the ``-t``
option) to the tree representation of the output tests. A simple transformer -
that inserts a space after every unparser rule - is provided by grammarinator
(``grammarinator.runtime.simple_space_transformer``).

As a final thought, one must not forget that the original purpose of grammars
is the syntax-wise validation of various inputs. As a consequence, these
grammars encode syntactic expectations only, and not semantic rules. If we
still want to add semantic knowledge into the generated test, then we can
inherit custom fuzzers from the generated ones and redefine methods
corresponding to lexer or parser rules in ways that encode the required
knowledge (e.g.: HTMLCustomUnparser_).

.. _HTMLCustomUnparser: examples/fuzzer/HTMLCustomUnparser.py

Working Example
===============

The repository contains a minimal example_ to generate HTML files. To give it
a try, run the processor first::

    grammarinator-process examples/grammars/HTMLLexer.g4 \
    examples/grammars/HTMLParser.g4 -o examples/fuzzer/


Then, use the generator to produce test cases::

    grammarinator-generate -l examples/fuzzer/HTMLCustomUnlexer.py \
    -p examples/fuzzer/HTMLCustomUnparser.py -r htmlDocument \
    -o examples/tests/test_%d.html -t HTMLUnparser.html_space_transformer -n 100 -d 20

.. _example: examples/


Compatibility
=============

*grammarinator* was tested on:

* Linux (Ubuntu 16.04 / 18.04)
* Mac OS X (Sierra 10.12 / High Sierra 10.13 / Mojave 10.14)


Citations
=========

Background on *grammarinator* is published in (R. Hodovan, A. Kiss, T. Gyimothy:
"Grammarinator: A Grammar-Based Open Source Fuzzer", A-TEST 2018).


Copyright and Licensing
=======================

Licensed under the BSD 3-Clause License_.

.. _LICENSE: LICENSE.rst
