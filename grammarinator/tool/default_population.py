# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import glob
import logging
import os
import pickle
import random

from copy import deepcopy
from os.path import basename, join
from uuid import uuid4

from ..runtime import Population, RuleSize, UnparserRule

logger = logging.getLogger(__name__)


class DefaultTree:

    def __init__(self, root):
        """
        :param Rule root: Root of the tree.
        """
        self.root = root
        self.nodes_by_name = None
        self.node_levels = None
        self.node_depths = None
        self.token_counts = None

    def __deepcopy__(self, memo):
        tree = DefaultTree(deepcopy(self.root, memo=memo))
        tree.annotate()
        return tree

    def annotate(self):
        """
        Build a lookup table to index nodes by their name. Furthermore, compute
        various depth information of nodes needed by
        :meth:`Population.select_to_mutate` and
        :meth:`Population.select_to_recombine`.
        """
        def _annotate(current, level):
            self.node_levels[current] = level

            if current.name not in self.nodes_by_name:
                self.nodes_by_name[current.name] = set()
            self.nodes_by_name[current.name].add(current)

            self.node_depths[current] = 0
            self.token_counts[current] = 0
            if isinstance(current, UnparserRule):
                for child in current.children:
                    _annotate(child, level + 1)
                    self.node_depths[current] = max(self.node_depths[current], self.node_depths[child] + 1)
                    self.token_counts[current] += self.token_counts[child] if isinstance(child, UnparserRule) else child.size.tokens + 1

        self.nodes_by_name = {}
        self.node_levels = {}
        self.node_depths = {}
        self.token_counts = {}
        _annotate(self.root, 0)

    @staticmethod
    def load(fn):
        """
        Load tree from file.

        :param str fn: Path to the file containing the tree.
        :return: The loaded tree.
        :rtype: DefaultTree
        """
        with open(fn, 'rb') as f:
            return pickle.load(f)

    def save(self, fn):
        """
        Annotate and save a tree into file if its depth is less than ``max_depth``.

        :param str fn: File path to save the tree to.
        """
        self.annotate()
        with open(fn, 'wb') as f:
            pickle.dump(self, f)

    def print(self):
        """
        Print the structure of the tree (for debugging purposes).
        """
        def _walk(node):
            nonlocal indent

            if isinstance(node, UnparserRule):
                print(f'{"|  " * indent}{node.name}')
                indent += 1
                for child in node.children:
                    _walk(child)
                indent -= 1

            else:
                print(f'{"|  " * indent}{node.name or ""}{":" if node.name else ""}{node.src!r}')

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


class DefaultPopulation(Population):
    """
    File system-based population that pickles trees to ``.grt`` files in a
    directory. The selection strategy used for mutation and recombination is
    purely random.
    """

    _extension = 'grt'

    def __init__(self, directory, min_sizes=None):
        """
        :param str directory: Path to the directory containing the trees.
        :param dict[str,RuleSize] min_sizes: Minimum size of rules.
        """
        self._directory = directory
        os.makedirs(directory, exist_ok=True)
        self._files = glob.glob(join(self._directory, f'*.{self._extension}'))
        self._min_sizes = min_sizes or {}

    def can_mutate(self):
        """
        Check whether there is at least a single individual in the population.
        """
        return len(self._files) > 0

    def can_recombine(self):
        """
        Check whether there are at least two individuals in the population.
        """
        return len(self._files) > 1

    def select_to_mutate(self, limit, root=None):
        """
        Randomly select an individual of the population to be mutated (unless
        ``root`` is not None, in which case the tree to be mutated is fixed).
        Then randomly select a node that should be re-generated.
        """
        if root:
            tree = DefaultTree(root)
            tree.annotate()
        else:
            tree_fn = self._random_individuals(n=1)[0]
            tree = DefaultTree.load(tree_fn)

        options = self._filter_nodes(tree, (node for name in tree.nodes_by_name for node in tree.nodes_by_name[name]), limit)
        if options:
            mutated_node = random.choice(options)
            return mutated_node, RuleSize(depth=tree.node_levels[mutated_node], tokens=tree.token_counts[tree.root] - tree.token_counts[mutated_node])

        # If selection strategy fails, we return the root of the loaded tree.
        # This will practically cause a fallback to discard the whole tree and
        # generate a brand new one instead.
        logger.debug('Could not choose node to mutate.')
        return tree.root, RuleSize()

    def select_to_recombine(self, limit, *roots):
        """
        Randomly select two individuals of the population to be recombined
        (unless maximum two ``roots`` positional arguments are specified, in
        which case one or both of the trees to be recombined are fixed). Then
        randomly select two compatible nodes from each.
        """
        if len(roots) > 2:
            raise ValueError(f'too many roots ({len(roots)})')
        trees = []
        for root in roots:
            tree = DefaultTree(root)
            tree.annotate()
            trees.append(tree)
        for tree_fn in self._random_individuals(n=2 - len(trees)):
            tree = DefaultTree.load(tree_fn)
            trees.append(tree)
        recipient_tree, donor_tree = trees[0], trees[1]

        common_types = set(recipient_tree.nodes_by_name.keys()).intersection(set(donor_tree.nodes_by_name.keys()))
        recipient_options = self._filter_nodes(recipient_tree, (node for rule_name in common_types for node in recipient_tree.nodes_by_name[rule_name]), limit)
        # Shuffle suitable nodes with sample.
        for recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            donor_options = tuple(donor_tree.nodes_by_name[recipient_node.name])
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth limit.
                if (recipient_tree.node_levels[recipient_node] + donor_tree.node_depths[donor_node] <= limit.depth
                        and recipient_tree.token_counts[recipient_tree.root] - recipient_tree.token_counts[recipient_node] + donor_tree.token_counts[donor_node] < limit.tokens):
                    return recipient_node, donor_node

        # If selection strategy fails, we return the roots of the two loaded
        # trees. This will practically cause the whole donor tree to be the
        # result of recombination.
        logger.debug('Could not find node pairs to recombine.')
        return recipient_tree.root, donor_tree.root

    def add_individual(self, root, path=None):
        """
        Save the tree to a new file. The name of the tree file is determined
        based on the pathname of the corresponding test case. From the pathname
        of the test case, the base name is kept up to the first period only. If
        no file name can be determined, the population class name is used as a
        fallback. To avoid naming conflicts, a unique identifier is concatenated
        to the file name.
        """
        if path:
            path = basename(path)
        if path:
            path = path.split('.')[0]
        if not path:
            path = type(self).__name__

        tree_path = join(self._directory, f'{path}.{uuid4().hex}.{self._extension}')
        DefaultTree(root).save(tree_path)
        self._files.append(tree_path)

    # Select ``n`` individuals from the population.
    def _random_individuals(self, n):
        return random.sample(self._files, n)

    # Filter items from ``nodes`` that can be regenerated within the current
    # maximum depth and token limit (except 'EOF' and '<INVALID>' nodes).
    def _filter_nodes(self, tree, nodes, limit):
        return [node for node in nodes
                if node.name is not None
                and node.parent is not None
                and node.name not in ['EOF', '<INVALID>']
                and tree.node_levels[node] + self._min_sizes.get(node.name, RuleSize(0, 0)).depth < limit.depth
                and tree.token_counts[tree.root] - tree.token_counts[node] + self._min_sizes.get(node.name, RuleSize(0, 0)).tokens < limit.tokens]
