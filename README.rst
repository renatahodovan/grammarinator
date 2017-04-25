=============
Grammarinator
=============
*ANTLRv4 grammar-based test generator*

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

Clone the project and run setuptools::

    python setup.py install


Usage
=====

As a first step, *grammarinator* takes an ANTLR_ v4 grammar and creates a test
generator script in Python3. Such a generator can be inherited later to
customize it further if needed.

Example usage to create a test generator::

    grammarinator-process <grammar-file(s)> -o <output-directory>

After having generated and optionally customized a fuzzer, it can be executed either
by the ``grammarinator-generate`` script or by instantiating it manually.

Example usage of the builtin ``grammarinator-generate``::

    grammarinator-generate -l <unlexer> -p <unparser> -r <start-rule> \
    -o <output-pattern> -n <number-of-tests> \
    -t grammarinator.runtime.simple_space_transformer


Grammarinator uses the ANTLR_ v4 grammar format as its input, which makes
existing grammars (lexer and parser rules) easily reusable. However, because
of the inherently different goals of a fuzzer and a parser, inlined code
(actions and conditions, header and member blocks) are most probably not
reusable, or even preventing proper execution. For first experiments with
existing grammar files, ``grammarinator-process`` supports the command-line
option ``--no-actions``, which skips all such code blocks during fuzzer
generation. Once inlined code is tuned for fuzzing, that option may be omitted.

Working Example
===============

The repository contains a minimal example_ to generate HTML files. To give it
a try, run the processor first::

    grammarinator-process examples/grammars/HTMLLexer.g4 \
    examples/grammars/HTMLParser.g4 -o examples/fuzzer/


Then, use the generator to produce test cases::

    grammarinator-generate -l examples/fuzzer/HTMLCustomUnlexer.py \
    -p examples/fuzzer/HTMLCustomUnparser.py -r htmlDocument \
    -o examples/tests/test_%d.html -t HTMLUnparser.html_space_transformer -n 100

.. _example: examples/


Compatibility
=============

*grammarinator* was tested on:

* Linux (Ubuntu 16.04)
* Mac OS Sierra (10.12.4).


Copyright and Licensing
=======================

See LICENSE_.

.. _LICENSE: LICENSE.rst
