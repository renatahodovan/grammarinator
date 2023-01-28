===========
Serializers
===========

Serializers in Grammarinator have the responsibility of generating string
representations from Grammarinator trees. These string representations serve as
the content for the output test cases. Serializers are implemented as functions
that take the root node of the tree as input and construct the output string by
traversing the tree.

When using the :ref:`grammarinator-generate <grammarinator-generate>` script,
the serializer can be specified using the ``--serializer`` CLI flag. When using
Grammarinator from the API, the serializer can be defined in the constructor of
:class:`grammarinator.tool.GeneratorTool`.

A default serializer implementation is available at
:func:`grammarinator.runtime.simple_space_serializer`. This serializer produces
output where tokens are separated by spaces.
