# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

class Population:
    """
    Abstract base class of populations that store test cases in tree form (i.e.,
    individuals) and can select trees (and nodes in trees) for mutation or
    recombination based on some strategy.
    """

    def can_mutate(self):
        """
        Query the population whether it has inividuals that can be mutated.

        Raises :exc:`NotImplementedError` by default.

        :return: Whether the population has individuals that can be mutated.
        :rtype: bool
        """
        raise NotImplementedError()

    def can_recombine(self):
        """
        Query the population whether it has individuals that can be recombined.

        Raises :exc:`NotImplementedError` by default.

        :return: Whether the population has individuals that can be recombined.
        :rtype: bool
        """
        raise NotImplementedError()

    def select_to_mutate(self, limit):
        """
        Select an individual of the population to be mutated and select a node
        in it that should be re-generated.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.RuleSize limit: The limit on the depth of
            the trees and on the number of tokens (number of unlexer rule
            calls), i.e., it must be possible to finish generation from the
            selected node so that the overall depth and token count of the
            tree does not exceed these limits.
        :return: The root of the sub-tree that should be re-generated and size
            information about the surroundings of the sub-tree (distance of the
            sub-tree from the root of the tree, number of tokens outside the
            sub-tree).
        :rtype: tuple[~grammarinator.runtime.Rule,~grammarinator.runtime.RuleSize]
        """
        raise NotImplementedError()

    def select_to_recombine(self, limit):
        """
        Select two individuals of the population to be recombined and select two
        compatible nodes from each. One of the individuals is called the
        recipient while the other is the donor. The sub-tree rooted at the
        selected node of the recipient should be discarded and replaced by the
        sub-tree rooted at the selected node of the donor.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.RuleSize limit: The limit on the depth of
            the trees and on the number of tokens (i.e., the depth of the
            recombined tree must not exceed this limit).
        :return: The roots of the sub-trees in the recipient and in the donor.
        :rtype: tuple[~grammarinator.runtime.Rule,~grammarinator.runtime.Rule]
        """
        raise NotImplementedError()

    def add_individual(self, root, path=None):
        """
        Add a tree to the population.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule root: Root of the tree to be added.
        :param str path: The pathname of the test case corresponding to the
            tree, if it exists. May be used for debugging.
        """
        raise NotImplementedError()
