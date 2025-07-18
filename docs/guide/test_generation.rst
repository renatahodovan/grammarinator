===============
Test Generation
===============

.. toctree::
  :hidden:

  listeners
  models
  transformers
  serializers

After :doc:`constructing a fuzzer<fuzzer_building>` and, if desired,
:doc:`creating a population<population>`, the ``grammarinator-generate``
utility or the ``grammarinator-generate-<name>`` binaries can be used to
generate test cases based on the format specified in the input grammar.

----------------
Python-based CLI
----------------

.. _grammarinator-generate:

.. describe:: The CLI of grammarinator-generate

.. runcmd:: python -m grammarinator.generate --help
   :syntax: none
   :replace: "generate.py/grammarinator-generate"

The ``grammarinator-generate`` utility requires a mandatory parameter which is
the reference to the generator class in the ``package.module.class`` format.
This means that the module (or package) of the class must be on the search
path for module files. If that is not the case, the appropriate directory
can be added to ``PYTHONPATH`` or specified using the ``--sys-path`` command
line argument.

The generation process starts from the rule specified by the ``--rule``
argument, or from the first parser rule if the ``--rule`` argument is not
provided.

The number of output test cases to be generated can be specified using the
``-n`` argument. The default value is ``1``, and it accepts both integers and
``inf`` for continuous generation.

The depth of the generated tree can be controlled using the ``--max-depth``
argument. If the generation cannot be performed within the provided depth,
an error will be raised.

The number of the output tokens (more precisiely, the number of the unlexer
rule calls during the generation) can be controlled using the ``--max-token``
argument. If the generation cannot be performed within the provided token
count, an error will be raised.

``--max-depth`` and ``--max-token`` can be defined at the same time. If
any of them is too strict by itself making the generation impossible, then
an error will be raised. However, if both of them are permissive enough
separately, but they are too strict together, then the limits will be
automatically updated to the minimal value that makes the generation possible.

The output test cases can be written to the file system using the ``--out``
argument, which allows the definition of the output file path. The ``%d``
wildcard can be used as a placeholder for the test case index, which will be
substituted by the generator. Alternatively, if the ``--stdout`` argument is
provided, the test cases will be printed to the standard output.

The behavior of the generator can be customized using :doc:`models <models>`
(``--model`` and ``--weights``), :doc:`listeners <listeners>` (``--listener``),
:doc:`transformers <transformers>` (``--transform``), and
:doc:`serializers <serializers>` (``--serialize``).

If a directory containing Grammarinator trees is specified using the
``--population`` argument and it is not empty, the utility enables the
:meth:`~grammarinator.tool.GeneratorTool.mutate` and
:meth:`~grammarinator.tool.GeneratorTool.recombine` operators for evolutionary
generation. If both ``--keep-trees`` and ``--population`` are set, the
generated trees will be saved to the population directory, allowing for
multiple modifications to be applied to the population items. Additionally,
if the population directory is empty but the ``--keep-trees`` argument is set,
the :meth:`~grammarinator.tool.GeneratorTool.generate` method will initialize the
population, enabling the use of mutation and recombination operators later on.
To disable specific operators, the ``--no-generate``, ``--no-mutate``, or
``--no-recombine`` arguments can be used.

-------------
C++-based CLI
-------------

In addition to the Python command line tool, Grammarinator also supports test
generation via **compiled C++ executables**. These are generated using the
``grammarinator-process`` tool with the ``--language hpp`` option, followed by
:ref:`building the generator<cpp_compilation>`.

Once built, a standalone executable is created with the name
``grammarinator-generate-<name>``, where ``<name>`` corresponds to the
generator class (e.g., ``grammarinator-generate-html``).

The C++ binary exposes a command-line interface that is **similar** to
``grammarinator-generate`` in terms of supported command line arguments
(max depth, max tokens, output pattern, population directory, etc.), but with
one key difference:

In the C++ backend, the generator class, :doc:`model class <models>`,
:doc:`listeners <listeners>`, :doc:`serializer <serializers>` and
:doc:`transformer <transformers>` are statically compiled into the binary.
These cannot be specified at runtime -- the binary is fully self-contained in
this regard. The rest of the generation parameters seen in
``grammarinator-generate``, such as output count, maximum depth, population
settings, etc., can be configured dynamically.

Example usage of a C++ generator::

  grammarinator-cxx/build/Release/bin/grammarinator-generate-html \
    -r htmlDocument -d 20 \
    -o examples/tests/test_%d.html -n 100

This command generates 100 HTML test cases using the ``htmlDocument`` start
rule, up to a maximum derivation depth of 20, and writes the results to the
``examples/tests/`` directory using a formatted file name.

..

    **Notes**

    - If you need to change the generator logic (e.g., use a different
      serializer or transformer), a new C++ binary must be rebuilt with
      those components linked in.
    - C++ binaries are useful in performance-critical or standalone fuzzing
      setups, including native
      :ref:`integration with libFuzzer<libfuzzer integration>`.
