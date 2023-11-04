# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class RuleSize:

    def __init__(self, depth=0, tokens=0):
        self.depth = depth
        self.tokens = tokens

    def __add__(self, other):
        return RuleSize(depth=self.depth + other.depth, tokens=self.tokens + other.tokens)

    def __iadd__(self, other):
        self.depth += other.depth
        self.tokens += other.tokens

    def __sub__(self, other):
        return RuleSize(depth=self.depth - other.depth, tokens=self.tokens - other.tokens)

    def __isub__(self, other):
        self.depth -= other.depth
        self.tokens -= other.tokens

    def __eq__(self, other):
        return self.depth == other.depth and self.tokens == other.tokens

    def __le__(self, other):
        # This defines a partial order (i.e., reflexive, antisymmetric, and transitive).
        # Not every pair of objects are comparable.
        return self.depth <= other.depth and self.tokens <= other.tokens

    def __lt__(self, other):
        # This defines a strict partial order (i.e., irreflexive, asymmetric, and transitive).
        # Not every pair of objects are comparable.
        return self.depth < other.depth and self.tokens < other.tokens


class Rule:
    """
    Base class of tree nodes.
    """

    def __init__(self, *, name, parent=None):
        """
        :param str name: Name of the node, i.e., name of the corresponding parser or lexer rule in the grammar.
        :param UnparserRule parent: Parent node object (default: None).

        :ivar str name: Name of the node, i.e., name of the corresponding parser or lexer rule in the grammar.
        :ivar UnparserRule parent: Parent node object.
        """
        self.name = name
        self.parent = parent
        if parent:
            parent += self

    @property
    def left_sibling(self):
        """
        Returns the left sibling of the node if any.

        :raises ValueError: if the current node has no parent or if it is
          detached from its parent (it is not among the children of the parent).

        :return: The left sibling of the current node.
        :rtype: Rule
        """
        try:
            self_idx = self.parent.children.index(self)
            return self.parent.children[self_idx - 1] if self_idx > 0 else None
        except ValueError:
            return None

    @property
    def right_sibling(self):
        """
        Returns the left sibling of the node if any.

        :raises ValueError: if the current node has no parent or if it is
          detached from its parent (it is not among the children of the parent).

        :return: The right sibling of the current node.
        :rtype: Rule
        """
        try:
            self_idx = self.parent.children.index(self)
            return self.parent.children[self_idx + 1] if self_idx < len(self.parent.children) - 1 else None
        except ValueError:
            return None

    def replace(self, node):
        """
        Replace the current node with ``node``.

        :param Rule node: The replacement node.
        :return: ``node``
        :rtype: Rule
        """
        if self.parent and node is not self:
            self.parent.children[self.parent.children.index(self)] = node
            node.parent = self.parent
            self.parent = None
        return node

    def delete(self):
        """
        Delete the current node from the tree.
        """
        if self.parent:
            self.parent.children.remove(self)
            self.parent = None


class UnparserRule(Rule):
    """
    Tree node representing a parser rule. It can have zero or more :class:`UnparserRule` or
    :class:`UnlexerRule` children.
    """

    def __init__(self, name, parent=None):
        """
        :param str name: Name of the corresponding parser rule in the grammar.
        :param UnparserRule parent: Parent node object (default: None).

        :ivar list[Rule] children: Children of the rule.
        """
        super().__init__(name=name, parent=parent)
        self.children = []

    @property
    def last_child(self):
        """
        Get or replace the last child of the current node.
        """
        return self.children[-1] if self.children else None

    @last_child.setter
    def last_child(self, node):
        self.children.pop().parent = None
        self.add_child(node)

    def insert_child(self, idx, node):
        """
        Insert node as child at position.

        :param int idx: Index of position to insert ``node`` to.
        :param Rule node: Node object to be inserted.
        """
        if not node:
            return

        node.parent = self
        self.children.insert(idx, node)

    def add_child(self, node):
        """
        Add node to the end of the list of the children.

        :param Rule node: Node to be added to children.
        """
        if node is None:
            return

        self.children.append(node)
        node.parent = self

    def add_children(self, nodes):
        """
        Add mulitple nodes to the end of the list of the children.

        :param list[Rule] nodes: List of nodes to be added to children.
        """
        for node in nodes:
            self.add_child(node)

    def __iadd__(self, item):
        """
        Support for ``+=`` operation to add one or more children to the current node. An alias to
        :meth:`add_child` or :meth:`add_children` depending on the type of ``child``.

        :param Rule or list[Rule] item: The node(s) to be added as child.
        :return: The current node with extended children.
        :rtype: Rule
        """
        if isinstance(item, list):
            self.add_children(item)
        else:
            self.add_child(item)
        return self

    def __str__(self):
        """
        Concatenates the string representation of the children.

        :return: String representation of the current rule.
        :rtype: str
        """
        return ''.join(str(child) for child in self.children)

    def __getattr__(self, item):
        # This check is needed to avoid infinite recursions when loading a tree
        # with pickle. In such cases, the loaded instance is prepared by
        # creating an empty object with the expected ``__class__`` and by
        # restoring the saved attributes (without calling ``__init__``).
        # During this operation, the ``__set_state__`` method of the target
        # class is tried to be called, if it exists. Otherwise, ``__getattr__``
        # throws an ``AttributeError``. However, if the instantiation of this
        # error object tries to access any field that is not yet added by
        # pickle, then it throws another ``AttributeError``, causing an
        # infinite recursion. Filtering for the field names, that are used
        # later in this method, eliminates the issue.
        if item in ['name', 'children']:
            raise AttributeError()

        result = [child for child in self.children if child.name == item]

        if not result:
            raise AttributeError(f'[{self.name}] No child with name {item!r} {[child.name for child in self.children]}.')

        return result[0] if len(result) == 1 else result


class UnlexerRule(Rule):
    """
    Tree node representing a lexer rule or token. It has a string constant set in its ``src`` field.
    """

    def __init__(self, *, name=None, parent=None, src=None):
        """
        :param str name: Name of the corresponding lexer rule in the grammar.
        :param UnparserRule parent: Parent node object (default: None).
        :param str src: String content of the lexer rule (default: "").

        :ivar str src: String content of the lexer rule.
        """
        self.src = src or ''
        self.size = RuleSize(depth=1 if src else 0, tokens=1 if src else 0)

        super().__init__(name=name, parent=parent)

    def __str__(self):
        """
        Return the string representation of an ``UnlexerRule``, which is simply ``self.src``.

        :return: String representation of ``UnlexerRule``.
        :rtype: str
        """
        return self.src
