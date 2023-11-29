# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

class Population:
    """
    Abstract base class of populations that store test cases in tree form (i.e.,
    individuals) and can select trees for mutation or recombination based on some strategy.
    """

    def __bool__(self):
        """
        Truth value testing of Populations.

        Raises :exc:`NotImplementedError` by default.

        :return: ``True`` if the population is not empty and ``False`` otherwise.
        :rtype: bool
        """
        raise NotImplementedError()

    def add_individual(self, root, annotations=None, path=None):
        """
        Add a tree to the population.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule root: Root of the tree to be added.
        :param object annotations: Data to be stored along the tree, if
            possible. No assumption should be made about the structure or the
            contents of the data, it should be treated as opaque.
        :param str path: The pathname of the test case corresponding to the
            tree, if it exists. May be used for debugging.
        """
        raise NotImplementedError()

    def select_individual(self):
        """
        Select an individual of the population.

        Raises :exc:`NotImplementedError` by default.

        :return: Root of the selected tree, and any associated information that
            was stored along the tree when it was added (if storing/restoring
            that information was possible).
        :rtype: tuple[~grammarinator.runtime.Rule,object]
        """
        raise NotImplementedError()
