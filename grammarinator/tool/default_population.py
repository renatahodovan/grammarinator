# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import glob
import logging
import os
import random

from os.path import basename, join
from uuid import uuid4

from ..runtime import Population, Rule, RuleSize, UnparserRule
from .tree_codec import AnnotatedTreeCodec, PickleTreeCodec

logger = logging.getLogger(__name__)


class Annotations:

    def __init__(self, root):
        def _annotate(current, level):
            self.node_levels[current] = level

            if current.name not in self.nodes_by_name:
                self.nodes_by_name[current.name] = []
            self.nodes_by_name[current.name].append(current)

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
        _annotate(root, 0)


class DefaultPopulation(Population):
    """
    File system-based population that saves trees into files in a directory. The
    selection strategy used for mutation and recombination is purely random.
    """

    def __init__(self, directory, extension, min_sizes=None, immutable_rules=None, codec=None):
        """
        :param str directory: Path to the directory containing the trees.
        :param str extension: Extension of the files containing the trees.
        :param dict[str,RuleSize] min_sizes: Minimum size of rules.
        :param set[str] immutable_rules: Set of immutable rule names.
        :param TreeCodec codec: Codec used to save trees into files (default:
            :class:`PickleTreeCodec`).
        """
        self._directory = directory
        self._extension = extension
        self._min_sizes = min_sizes or {}
        self._immutable_rules = set(immutable_rules) if immutable_rules else set()
        self._codec = codec or PickleTreeCodec()

        os.makedirs(directory, exist_ok=True)
        self._files = glob.glob(join(self._directory, f'*.{self._extension}'))

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
            annot = Annotations(root)
        else:
            root, annot = self._load_tree(self._random_individuals(n=1)[0])

        options = self._filter_nodes((node for nodes in annot.nodes_by_name.values() for node in nodes), root, annot, limit)
        if options:
            mutated_node = random.choice(options)
            return mutated_node, RuleSize(depth=annot.node_levels[mutated_node], tokens=annot.token_counts[root] - annot.token_counts[mutated_node])

        # If selection strategy fails, we return the root of the loaded tree.
        # This will practically cause a fallback to discard the whole tree and
        # generate a brand new one instead.
        logger.debug('Could not choose node to mutate.')
        return root, RuleSize()

    def select_to_recombine(self, limit, recipient_root=None, donor_root=None):
        """
        Randomly select two individuals of the population to be recombined
        (unless ``recipient_root`` or ``donor_root`` is not None, in which case
        one or both of the trees to be recombined are fixed). Then randomly
        select two compatible nodes from each.
        """
        roots = [recipient_root, donor_root]
        annots = [None, None]
        tree_fns = self._random_individuals(n=int(not recipient_root) + int(not donor_root))
        n = 0
        for i, root in enumerate(roots):
            if root:
                annots[i] = Annotations(root)
            else:
                roots[i], annots[i] = self._load_tree(tree_fns[n])
                n += 1
        recipient_root, recipient_annot = roots[0], annots[0]
        donor_root, donor_annot = roots[1], annots[1]

        common_types = sorted(set(recipient_annot.nodes_by_name.keys()).intersection(set(donor_annot.nodes_by_name.keys())))
        recipient_options = self._filter_nodes((node for rule_name in common_types for node in recipient_annot.nodes_by_name[rule_name]), recipient_root, recipient_annot, limit)
        # Shuffle suitable nodes with sample.
        for recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            donor_options = donor_annot.nodes_by_name[recipient_node.name]
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth limit.
                if (recipient_annot.node_levels[recipient_node] + donor_annot.node_depths[donor_node] <= limit.depth
                        and recipient_annot.token_counts[recipient_root] - recipient_annot.token_counts[recipient_node] + donor_annot.token_counts[donor_node] < limit.tokens):
                    return recipient_node, donor_node

        # If selection strategy fails, we return the roots of the two loaded
        # trees. This will practically cause the whole donor tree to be the
        # result of recombination.
        logger.debug('Could not find node pairs to recombine.')
        return recipient_root, donor_root

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
        self._save_tree(tree_path, root)
        self._files.append(tree_path)

    # Select ``n`` individuals from the population.
    def _random_individuals(self, n):
        return random.sample(self._files, n)

    # Filter items from ``nodes`` that can be regenerated within the current
    # maximum depth and token limit (except 'EOF' and '<INVALID>' nodes).
    def _filter_nodes(self, nodes, root, annot, limit):
        return [node for node in nodes
                if node.parent is not None
                and node.name not in self._immutable_rules
                and node.name not in [None, '<INVALID>']
                and annot.node_levels[node] + self._min_sizes.get(node.name, RuleSize(0, 0)).depth < limit.depth
                and annot.token_counts[root] - annot.token_counts[node] + self._min_sizes.get(node.name, RuleSize(0, 0)).tokens < limit.tokens]

    def _load_tree(self, fn):
        with open(fn, 'rb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                root, annot = self._codec.decode_annotated(f.read())
            else:
                root, annot = self._codec.decode(f.read()), None
            if not annot:
                annot = Annotations(root)
            assert isinstance(root, Rule), root
            assert isinstance(annot, Annotations), annot
            return root, annot

    def _save_tree(self, fn, root):
        with open(fn, 'wb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                f.write(self._codec.encode_annotated(root, Annotations(root)))
            else:
                f.write(self._codec.encode(root))
