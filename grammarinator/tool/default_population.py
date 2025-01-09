# Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
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

from ..runtime import Annotations, Individual, Population, Rule
from .tree_codec import AnnotatedTreeCodec, PickleTreeCodec

logger = logging.getLogger(__name__)


class DefaultPopulation(Population):
    """
    File system-based population that saves trees into files in a directory. The
    selection strategy used for mutation and recombination is purely random.
    """

    def __init__(self, directory, extension, codec=None):
        """
        :param str directory: Path to the directory containing the trees.
        :param str extension: Extension of the files containing the trees.
        :param TreeCodec codec: Codec used to save trees into files (default:
            :class:`PickleTreeCodec`).
        """
        self._directory = directory
        self._extension = extension
        self._codec = codec or PickleTreeCodec()

        os.makedirs(directory, exist_ok=True)
        self._files = glob.glob(join(self._directory, f'*.{self._extension}'))

    def empty(self):
        """
        Check whether the population contains no individuals.
        """
        return len(self._files) == 0

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

        fn = join(self._directory, f'{path}.{uuid4().hex}.{self._extension}')
        self._save(fn, root)
        self._files.append(fn)

    def select_individual(self):
        """
        Randomly select an individual of the population and create a
        DefaultIndividual instance from it.

        :return: DefaultIndividual instance created from a randomly selected population item.
        :rtype: DefaultIndividual
        """
        return DefaultIndividual(self, random.sample(self._files, k=1)[0])

    def _save(self, fn, root):
        with open(fn, 'wb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                f.write(self._codec.encode_annotated(root, Annotations(root)))
            else:
                f.write(self._codec.encode(root))

    def _load(self, fn):
        with open(fn, 'rb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                root, annot = self._codec.decode_annotated(f.read())
            else:
                root, annot = self._codec.decode(f.read()), None
            assert isinstance(root, Rule), root
        return root, annot


class DefaultIndividual(Individual):
    """
    Individual subclass presenting a file-based population individual, which
    maintains both the tree and the associated annotations. It is responsible
    for loading and storing the tree and its annotations with the appropriate
    tree codec in a lazy manner.
    """

    def __init__(self, population, name):
        """
        :param DefaultPopulation population: The population this individual
            belongs to.
        :param str name: Path to the encoded tree file.
        """
        super().__init__(name)
        self._population = population
        self._root = None

    @property
    def root(self):
        """
        Get the root of the tree. Return the root if it is already loaded,
        otherwise load it immediately.

        :return: The root of the tree.
        :rtype: ~grammarinator.runtime.Rule
        """
        if not self._root:
            self._root, self._annot = self._population._load(self.name)
        return self._root
