===============
Fuzzer Building
===============

.. toctree::
  :hidden:

  grammar_overview
  actions

Fuzzers in Grammarinator are constructed in two main stages:

1. A *generator* class is created from an ANTLRv4 grammar.
2. In the case of the C++ backend, the generated source code is compiled into
   standalone executables or libraries.

The following sections describe each step in detail.

-------------------------------------
Generator Creation from ANTLR Grammar
-------------------------------------

In both Python and C++ backends, the first step is to convert the ANTLR grammar
into a generator class. This generator encapsulates the logic for producing
derivation trees from the grammar rules.

In the **Python backend**, this generator is an instance of
:class:`~grammarinator.runtime.Generator`, which will be utilized in the
subsequent step where test cases are produced using the
:ref:`grammarinator-generate<grammarinator-generate>` command.

In the **C++ backend**, a corresponding ``Generator`` class is generated as a
header-only C++ file (e.g., ``HTMLGenerator.hpp``). While this class does not
yet have dedicated API documentation, it mirrors the structure and behavior of
the Python generator and is used by the compiled fuzzing tools
(e.g., the ``grammarinator-generate-html`` binary and
:ref:`libFuzzer integration<libfuzzer integration>`).

The generator class -- whether Python or C++ -- is automatically produced by
the ``grammarinator-process`` command line utility. This tool loads and
interprets the input grammar, generating a corresponding generator written in
the target language. The output generator will consist of a class definition,
named based on the grammar's name in the format ``<grammarName>Generator`` and
methods corresponding to each rule defined in the grammar.


.. describe:: The CLI of grammarinator-process

.. runcmd:: python -m grammarinator.process --help
   :syntax: none
   :replace: "process.py/grammarinator-process"

The usage of ``grammarinator-process`` is straigthforward: it processes the
specified grammars encoded with the ``--encoding`` option (default: ``utf-8``)
and generates the output in the directory specified by ``--out`` (default is the
current working directory). The generated code is written in the programming
language specified by ``--language`` (currently, the available options are
``py`` for Python and ``hpp`` for C++).

If the grammar contains parser-specific or unnecessary inline actions, they
can be ignored by using the ``--no-actions`` option. The grammars can also
include an :ref:`options<options>` section, where values can be extended or
overridden from the command-line interface (CLI) using the ``-D OPT=VAL``
argument.

If a grammar imports other grammars from a different directory, the directory
path needs to be defined using the ``--lib`` argument.

Additionally, the output grammar can be automatically formatted to follow the
PEP8 style recommendations by using the ``--pep8`` option.

.. _cpp_compilation:

------------------
Compilation in C++
------------------

Once the generator header has been created from the grammar, the next step in
the C++ workflow is to compile it into a usable binary or library. This is
done using the ``build.py`` utility script, which is located in
``grammarinator-cxx/dev/``.

.. _build.py:

.. describe:: The CLI of grammarinator-cxx/dev/build.py

.. runcmd:: python ../grammarinator-cxx/dev/build.py --help
   :syntax: none

The ``build.py`` script takes the configuration of the desired generator and
optional components and compiles a standalone binary from them.

**Component Configuration**

The following command-line arguments define the components that should be built
into the resulting binary:

- ``--generator`` (**required**): Fully qualified name of the generator class,
  e.g., ``HTMLGenerator``.

- ``--model``, ``--listener``, ``--transformer``, ``--serializer`` (*optional*):
  Fully qualified names of additional components to be compiled into the binary
  (e.g., ``grammarinator::runtime::NoSpaceSerializer``).

- ``--includedir`` (**required**): Directory that contains the source headers of
  all specified components. Only one include directory can be specified, so it is
  recommended to place all related source files (generator, serializer, etc.)
  in the same folder.

If any component beyond the generator is specified, an additional argument is
required:

- ``--include`` (*optional*): A header file (e.g., ``HTMLConfig.hpp``) that
  explicitly includes all component headers. This is **only needed** if any
  component other than the generator is customized. The file must reside in the
  directory specified by ``--includedir``.

For example, if using a custom serializer and transformer, your config file
(``HTMLConfig.hpp``) might look like::

   #include "HTMLGenerator.hpp"
   #include "HTMLSpaceSerializer.hpp"

**Binary Output**

Depending on the build flags, the following outputs may be generated:

- With ``--tools``:

  - ``grammarinator-generate-<name>``: standalone blackbox generator

- With ``--grlf``:

  - ``libgrlf-<name>.a``: static library to define
    ``LLVMFuzzerCustomMutator`` or ``LLVMFuzzerCustomCrossover`` (useful for
    :ref:`libFuzzer integration<libfuzzer integration>`)

- With ``--fuzznull``:

  - ``fuzznull-<name>``: dummy libFuzzer binary for integration testing

All outputs are written to the ``build/<Release|Debug>/bin`` and
``build/<Release|Debug>/lib`` directories.

**Compiler Requirements**

Clang is required for building libFuzzer-linked binaries due to the use of
``-fsanitize=fuzzer``. You can specify it by setting the environment variable::

   CXX=clang++ python3 grammarinator-cxx/dev/build.py ...

