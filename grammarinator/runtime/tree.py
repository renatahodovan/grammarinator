# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import pickle

from copy import deepcopy
from math import inf


class Tree(object):

    extension = '.grt'

    def __init__(self, root):
        """
        :param Rule root: Root of the generated tree.
        """
        self.root = root
        self.node_dict = None

    def __deepcopy__(self, memo):
        tree = Tree(deepcopy(self.root, memo=memo))
        tree.annotate()
        return tree

    def annotate(self):
        """
        Add a lookup table to the current tree indexing its nodes by their name.
        Furthermore, it calculates various depth information of nodes needed by
        :meth:`grammarinator.Generator.mutate` and :meth:`grammarinator.Generator.recombine`.
        """
        def _annotate(current, level):
            """
            :param current: The node to start annotation from (initially it's the root).
            :param level: Level to start annotation from.
            :return: Depth of the current node.
            """
            current.level = level
            level += 1

            if current.name not in self.node_dict:
                self.node_dict[current.name] = set()
            self.node_dict[current.name].add(current)

            current.depth = 0
            if current.children:
                for child in current.children:
                    child.depth = _annotate(child, level)
                    current.depth = max(current.depth, child.depth + 1)

            return current.depth

        self.node_dict = {}
        _annotate(self.root, 0)

    @staticmethod
    def load(fn):
        """
        Load tree from file.

        :param str fn: Path to the file containing the tree.
        :return: The loaded tree.
        :rtype: Tree
        """
        with open(fn, 'rb') as f:
            return pickle.load(f)

    def save(self, fn, max_depth=inf):
        """
        Annotate and save a tree into file if its depth is less than ``max_depth``.

        :param str fn: File path to save the tree to.
        :param int or float max_depth: Maximum depth that is allowed to save (default: ``inf``).
        :return: Returns True if saving succeded, otherwise False.
        :rtype: bool
        """
        self.annotate()

        if self.root.depth <= max_depth:
            with open(fn, 'wb') as f:
                pickle.dump(self, f)
            return True
        return False

    def print(self):
        """
        Print the structure of the tree (for debugging purposes).
        """
        def _walk(node):
            nonlocal indent

            if isinstance(node, UnparserRule):
                print(f'{"  " * indent}{node.name}')
                indent += 1
                for child in node.children:
                    _walk(child)
                indent -= 1

            else:
                toplevel_unlexerrule = not node.parent or isinstance(node.parent, UnparserRule)
                if toplevel_unlexerrule:
                    print(f'{"  " * indent}{node.name or ""}{":" if node.name else ""}"', end='')

                if node.src is not None:
                    print(node.src, end='')
                else:
                    for child in node.children:
                        _walk(child)

                if toplevel_unlexerrule:
                    print('"')

        indent = 0
        _walk(self.root)

    def __str__(self):
        """
        Create the string representation of the tree starting from the
        root node. Return a raw token sequence without any formatting.

        :return: String representation of the tree.
        :rtype: str
        """
        return str(self.root)


class Rule(object):
    """
    Base class of tree nodes.
    """

    def __init__(self, *, name, parent=None):
        """
        :param str name: Name of the node, i.e., name of the corresponding parser or lexer rule in the grammar.
        :param Rule parent: Parent node object (default: None).

        :ivar str name: Name of the node, i.e., name of the corresponding parser or lexer rule in the grammar.
        :ivar Rule parent: Parent node object.
        :ivar list[Rule] children: Children of the rule.
        """
        self.name = name
        self.parent = parent
        if parent:
            parent += self
        self.children = []
        self.level = None
        self.depth = None

    def __iadd__(self, child):
        """
        Support for ``+=`` operation to add one or more children to the current node. An alias to
        :meth:`add_child` or :meth:`add_children` depending on the type of ``child``.

        :param Rule or list[Rule] child: The node(s) to be added as child.
        :return: The current node with extended children.
        :rtype: Rule
        """
        if isinstance(child, list):
            self.add_children(child)
        else:
            self.add_child(child)
        return self

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
        :param Rule node: Node object to be insert.
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


class UnparserRule(Rule):
    """
    Tree node representing a parser rule. It can have zero or more :class:`UnparserRule` or
    :class:`UnlexerRule` children.
    """


class UnlexerRule(Rule):
    """
    Tree node representing a lexer rule or token. It either has one or more further :class:`UnlexerRule`
    children or - if it does not have any children - it has a string constant set in its ``src`` field.
    """

    def __init__(self, *, name=None, parent=None, src=None):
        """
        :param str name: Name of the corresponding lexer rule in the grammar.
        :param Rule parent: Parent node object (default: None).
        :param str src: String content of the lexer rule (default: None).

        :ivar str src: String content of the lexer rule.
        """
        super().__init__(name=name, parent=parent)
        self.src = src

    def __str__(self):
        """
        Return the string representation of an ``UnlexerRule``. It is either ``self.src`` for simple tokens
        or the concatenation of the string representation of the children for more complex production rules.

        :return: String representation of ``UnlexerRule``.
        :rtype: str
        """
        return self.src or super().__str__()
