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
utility can be used o generate test cases based on the format specified in the
input grammar.

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

The output test cases can be written to the file system using the ``--out``
argument, which allows the definition of the output file path. The ``%d``
wildcard can be used as a placeholder for the test case index, which will be
substituted by the generator. Alternatively, if the ``--stdout`` argument is
provided, the test cases will be printed to the standard output.

The behavior of the generator can be customized using :doc:`models <models>`
(``--model`` and ``--cooldown``), :doc:`listeners <listeners>`
(``--listener``), :doc:`transformers <transformers>` (``--transform``), and
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
