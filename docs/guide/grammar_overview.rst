================
Grammar Overview
================

Grammarinator supports `ANTLRv4 grammar`_ files as input, but it does not
necessarily utilize all of the grammar's features for fuzzer and test
generation purposes.

In the following, the supported features are introduced.

.. code-block:: text
   :caption: The structure of ANTLRv4 grammars

    /** Optional javadoc style comment */
    grammar GrammarName;

    options {key1=value1; key2=value2; /* ... */ }

    import Grammar1, Grammar2 /* , ... */;

    tokens {Imag1, Imag2 /* , ... */ }

    @header { /* code block in the target language */ }
    @members { /* code block in the target language */ }

    // Parser and lexer rules, possibly intermingled.
    rule1: alt1 | alt2 /* | ... */ ;
    // ...
    ruleN: /* ... */ ;


The grammar starts with the declaration of its type and name. The declaration
syntax looks like:

.. code-block:: antlr

    grammarDecl : ('lexer' | 'parser')? 'grammar' grammarName ';' ;


The name of the grammar and the name of the containing file must match, with
the file having the extension ``.g4``. The type of the grammar can be indicated
as a prefix before the ``grammar`` keyword. It can be specified as ``lexer``
for a lexer grammar, ``parser`` for a parser grammar, or omitted for a combined
grammar.

A combined grammar can include both lexer and parser rules, while a lexer
grammar should only contain lexer rules, and a parser grammar should only
contain parser rules. In the case of Grammarinator, the name of the grammar
is used to generate the name of the corresponding fuzzer class, following
the format ``<GrammarName>Generator``.


Options, Imports, Tokens, Named Actions
=======================================

After the grammar definition, the ANTLR grammar file may include optional
sections such as options, imports, tokens, and named actions. These
sections can appear in any order.

.. _options:

The **options** section allows for customizing and configuring various aspects
of the grammar. Options are defined using a key-value pair syntax, similar to
a dictionary. The supported keys for the ``options`` section in Grammarinator
are as follows:

  1) ``superClass``: This option defines the ancestor class of the generator
     created from the current grammar.
  2) ``dot``: This option specifies how the generator should handle the
     wildcard character ``.`` in the grammar.
     The "dot" option accepts three possible values:

     - ``any_ascii_letter``: generates any ASCII letter
     - ``any_ascii_char``: generates any ASCII character
     - ``any_unicode_char``: generates any Unicode character

**Imports** allow for the inclusion of external grammars into the importing
grammar. This means that the rules defined in the imported grammar will be
treated as if they were part of the importing grammar.
Consequently, the methods generated for these imported rules will become
members of the generated fuzzer.

The **tokens** section can be used to define imaginary tokens, which are token
types that do not have an associated lexical rule. Grammarinator will generate
empty methods for these imaginary tokens. These empty methods serve as
placeholders that can be expanded and customized in the subclasses.

ANTLRv4 supports **named actions** in the global scope. Two named actions are
supported: ``header`` and ``members``. For details on named actions see
:doc:`actions`.


Rules
=====

Next, the structure of rules is discussed. For the ANTLR documentation of
rules, see `lexer rules`_ and `parser rules`_.

There are two types of rules: lexer rules and parser rules. (Actually, ANTLR
defines a specific lexer rule in addition, called fragment rule, which is
treated the same as lexer rules in Grammarinator). Lexer rule names
must start with capital letters, while parser rules start with lowercase
letters.

Both lexer and parser rules consist of zero or more alternatives, separated
by the ``|`` symbol, like this: ``alt1 | alt2 | ...``.

Alternatives (both in lexer and parser rules) are built from the following elements:

  1) **Reference**: Referring to other lexer or parser rules. Lexer rules can
     only reference lexer rules, while parser rules can reference both lexer
     and parser rules.
  2) **Literals**: Lexer rules and parser rules in combined grammars
     can define implicit literals by enclosing them in single quotes
     (e.g., ``'literal'``).
  3) **Dot**: The ``dot`` wildcard behaves differently in parser and in
     lexer rules. In lexer rules, it represents an arbitrary single character.
     Its behavior can be customized using the ``dot`` option. See the ``dot``
     key in `options`_ for details. However, if it is placed in a parser rule,
     then it represents an arbitrary token of the grammar. Since Grammarinator
     does not keep track of lexer modes (yet), the token is selected from all
     tokens available in all lexer modes.
  4) **Parentheses**: Grouping parts of rules using parentheses to create
     blocks (e.g., ``(rule1 | 'literal')``).
  5) **Quantifiers**: Applying quantifiers to references, literals, and blocks
     to specify repetition:

      a) ``*`` (Kleene-star): The preceding item can be repeated zero or
         more times.
      b) ``+`` (Kleene-plus): The preceding item must be repeated one
         or more times.
      c) ``?`` (optional): The preceding item is optional, it may either
         be omitted or it may appear once.

  6) **Actions**: Inline code blocks in the target language used to define
     operations that cannot be expressed with grammar rules alone.
     For details see the chapter :doc:`actions`.
  7) **Semantic predicates**: Inline code blocks in the target language used
     to guide the selection of alternatives in ways that cannot be expressed
     with grammar rules alone.
     For details see the chapter :doc:`actions`.
  8) **Variables**: Variables in grammar rules allow to save subtrees and use
     them later within the same rule. Variables are denoted by a dollar sign
     (``$``) prefix when referring to them.

     The following example uses variables to match the opening and closing tag
     name of HTML tags:

    .. code-block:: antlr

      htmlElement
        : '<' open_tag=htmlTagName htmlAttribute* '>'
          htmlContent
          '</' htmlTagName {current.last_child.replace(deepcopy($open_tag))} '>'
        | ...
        ;


Lexer Rule Specific Items
-------------------------

  1) **Character range**: Defines character range in the form of ``'x'..'y'``,
     inclusively. Both ``x`` and ``y`` must be a single character or a unicode
     code point in the form ``\uXXXX`` or ``\u{XXXXXX}``.
  2) **Character set**: Defines a character set inside square brackets
     ``[...]``. It may contain single characters or ranges separated with
     ``-``. It supports the following special characters: ``\n``, ``\r``,
     ``\b``, ``\t``, ``\f`` and ``\uXXXX`` or ``\u{XXXXXX}``. ``]`` and ``\``
     must be escaped with ``\``, while ``-`` must be the first item if it is
     part of the set.
     Examples: ``[0-9a-fA-F]`` (hex digits) or ``[-a-zA-Z0-9.,;!?]``.
  3) **Inverted set**: Defines a character set with inverting another one. It
     is defined in the form ``~x`` where ``x`` can be a single character
     literal, a character range or a character set.
     Example: ``~[\r\n]`` means anything except line breaks.



.. _`ANTLRv4 grammar`: https://github.com/antlr/antlr4/blob/master/doc/index.md
.. _`lexer rules`: https://github.com/antlr/antlr4/blob/master/doc/lexer-rules.md
.. _`parser rules`: https://github.com/antlr/antlr4/blob/master/doc/parser-rules.md
