===============================
Actions and Semantic Predicates
===============================

Actions and semantic predicates are code blocks that are inserted into the
grammar and written in the target language. These code blocks provide
additional functionality and logic to the grammar rules.

-------
Actions
-------

Actions serve the purpose of defining operations that cannot be expressed
solely through grammar rules. Actions can be defined either anonymously
within rule definitions or within the global scope of the grammar (outside
of any rule definitions), prefixed with specific directives.


Anonymous Actions
=================

Anonymous actions, enclosed in curly braces (``{...}``), can be inserted into
the definition of lexer and parser rules. These code blocks are then copied
as-is, without any modifications, in the recognizer (when using ANTLR)
or in the generator (when using Grammarinator). Anonymous actions are used to
express specific operations associated with a particular grammar rule.


Named Actions
=============

Named actions are similar to anonymous actions in that they are also inline
code blocks enclosed in braces. However, instead of placing them inside rule
definitions, named actions are inserted into the global scope. These named
actions allow for the inclusion of custom code that can be utilized across
multiple rules or provide global functionality to the grammar. They are
prefixed with specific directives to indicate their purpose. These directives
can take one of two values: ``header`` or ``members``. These named actions can
be defined for both lexer/parser and combined grammars.

The syntax of named actions looks like:

.. code-block:: antlr

   namedAction: '@' (('lexer' | 'parser') '::'  )? ('header' | 'members') ;


While ANTLR differentiates between lexer, parser or combined grammar actions,
Grammarinator does not make any difference since it will generate a single
:class:`~grammarinator.runtime.Generator` subclass from the lexer and parser.
Hence, all the defined ``header`` and ``members`` actions will be
concatenated.

Grammarinator handles named actions as follows:

  1) The contents of ``header`` actions are placed immediately preceding the
     definition of the Generator subclass. These ``header`` actions can
     include imports, declarations of global variables, or other relevant
     code snippets.

  2) The contents of ``members`` actions are inserted into the fuzzer class
     to allow the definition of member fields and methods.


---------
Listeners
---------

Listeners provide an alternative to anonymous actions. Instead of inlining code
directly within the grammar, the code for listeners is defined in a separate
class, typically in a separate file. Listeners' methods are invoked before
and after recognizing or generating a rule, providing an opportunity to
perform custom actions at those specific points in the parsing or generating
process. This separation of code into listener classes allows for better
organization and modularity in grammar implementations.

For detailed information about Grammarinator listeners, please refer to the
documentation section dedicated to :doc:`listeners <listeners>`.

.. _semantic-predicates:

-------------------
Semantic predicates
-------------------

Semantic predicates are inline code blocks written in the target language
that guide the selection of alternatives. They are surrounded by ``{...}?``
and are placed into the lexer or parser rules of the grammar. In the case of
ANTLR, they are evaluated as booleans, enabling or disabling the selection
of a particular alternative when parsing. In Grammarinator, however, semantic
predicates are treated as weights and are evaluated as floats. When selecting
an alternative, the weights of all alternatives are normalized so that their
sum is 1, and then they are used as probabilities. If no semantic predicate
is defined for an alternative, its default weight is 1.0. Assigning the weight
of 0.0 to an alternative indicates that it is disabled.

In ANTLR, semantic predicates of parser rules are expected to be placed at the
beginning of alternatives, while predicates of lexer rules can be positioned
anywhere within the lexer rule definition. However, in case of Grammarinator,
semantic predicates are only interpreted if they are placed at the beginning
of an alternative, regardless of whether it is in a lexer or parser rule. This
approach is necessary due to the nature of code generation, as the generator
needs to determine the allowed alternatives at branching points.

Note: There are another ways of guiding alternative selection in Grammarinator:
using :doc:`models <models>` or subclassing the
:class:`grammarinator.runtime.Generator`.


.. rubric:: Example

The following example shows an excerpt from the ECMAScript grammar where
actions and semantic predicates are used to keep track of the language
structure and help choosing from the available statements.


.. code-block:: antlr-python
   :caption: Example grammar snippet using actions and predicates

    @members {
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.inside_function = 0
        self.inside_loop = 0
        self.inside_switch = 0
    }

    sourceElement
       : statement
       | {self.inside_function += 1} functionDeclaration {self.inside_function -= 1}
       ;

    statement
       : ...
       | {self.inside_loop += 1} iterationStatement {self.inside_loop -= 1}
       | {self.inside_loop}? continueStatement
       | {self.inside_loop or self.inside_switch}? breakStatement
       | {self.inside_function}? returnStatement
       | ...
       | {self.inside_switch += 1} switchStatement {self.inside_switch -= 1}
       | ...
       ;
