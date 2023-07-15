===============
Fuzzer Building
===============

To generate test cases from an ANTLRv4 grammar, the first step is to create a
generator object (instance of a :class:`~grammarinator.runtime.Generator`
subclass). This generator object will be utilized in the subsequent step,
where test cases are produced using the
:ref:`grammarinator-generate<grammarinator-generate>` command.

To create the generator class, you can make use of the
``grammarinator-process`` CLI utility. This utility loads and interprets the
input grammar, generating a corresponding generator written in the target
language (currently, only Python is supported). The output generator will
consist of a class definition, named based on the grammar's name in the format
``<grammarName>Generator`` and methods corresponding to each rule defined in
the grammar.


.. describe:: The CLI of grammarinator-process

.. runcmd:: python -m grammarinator.process --help
   :syntax: none
   :replace: "process.py/grammarinator-process"

The usage of ``grammarinator-process`` is straigthforward: it processes the
grammars defined as ``FILE`` encoded with the ``--encoding`` option
(default: ``utf-8``) and generates the output in the directory specified by
``--out`` (default is the current working directory). The generated code is
written in the programming language specified by ``--language`` (currently,
the only available option is ``py`` for Python).

If the grammar contains parser-specific or unnecessary inline actions, they
can be ignored by using the ``--no-actions`` option. The grammars can also
include an :ref:`options<options>` section, where values can be extended or
overridden from the command-line interface (CLI) using the ``-D OPT=VAL``
argument.

If a grammar imports other grammars from a different directory, the directory
path needs to be defined using the ``--lib`` argument.

Additionally, the output grammar can be automatically formatted to follow the
PEP8 style recommendations by using the ``--pep8`` option.

.. toctree::
  :hidden:

  grammar_overview
  actions
