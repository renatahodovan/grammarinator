# Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from __future__ import annotations

import glob
import logging
import os
import random

from os.path import basename, join

from ..runtime import Annotations, Individual, Population, Rule
from .tree_codec import AnnotatedTreeCodec, PickleTreeCodec, TreeCodec

logger = logging.getLogger(__name__)


class FilePopulation(Population):
    """
    File system-based population that saves trees into files in a directory. The
    selection strategy used for mutation and recombination is purely random.
    """

    def __init__(self, directory: str, extension: str, codec: TreeCodec | None = None) -> None:
        """
        :param directory: Path to the directory containing the trees.
        :param extension: Extension of the files containing the trees.
        :param codec: Codec used to save trees into files (default:
            :class:`PickleTreeCodec`).
        """
        self._directory: str = directory
        self._extension: str = extension
        self._codec: TreeCodec = codec or PickleTreeCodec()

        os.makedirs(directory, exist_ok=True)
        self._files = glob.glob(join(self._directory, f'*.{self._extension}'))

    def empty(self) -> bool:
        """
        Check whether the population contains no individuals.
        """
        return len(self._files) == 0

    def add_individual(self, root: Rule, path: str | None = None) -> None:
        """
        Save the tree to a new file. The name of the tree file is determined
        from the basename of the given path, or from the population class name
        if none is provided. The output file is saved with the appropriate
        extension defined by the current tree codec.
        """
        path = basename(path) if path else type(self).__name__
        fn = join(self._directory, f'{path}.{self._extension}')
        self._save(fn, root)
        self._files.append(fn)

    def select_individual(self, recipient: Individual | None = None) -> Individual:
        """
        Randomly select an individual of the population and create a
        DefaultIndividual instance from it.

        :param recipient: Unused.
        :return: DefaultIndividual instance created from a randomly selected
            population item.
        """
        return FileIndividual(self, random.sample(self._files, k=1)[0])

    def _save(self, fn: str, root: Rule) -> None:
        with open(fn, 'wb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                f.write(self._codec.encode_annotated(root, Annotations(root)))
            else:
                f.write(self._codec.encode(root))

    def _load(self, fn: str) -> tuple[Rule, Annotations | None]:
        with open(fn, 'rb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                root, annot = self._codec.decode_annotated(f.read())
            else:
                root, annot = self._codec.decode(f.read()), None
            assert isinstance(root, Rule), root
        return root, annot


class FileIndividual(Individual):
    """
    Individual subclass presenting a file-based population individual, which
    maintains both the tree and the associated annotations. It is responsible
    for loading and storing the tree and its annotations with the appropriate
    tree codec in a lazy manner.
    """

    def __init__(self, population: FilePopulation, name: str) -> None:
        """
        :param population: The population this individual belongs to.
        :param name: Path to the encoded tree file.
        """
        super().__init__()
        self._population: FilePopulation = population
        self._name: str = name

    @property
    def root(self) -> Rule:
        """
        Get the root of the tree. Return the root if it is already loaded,
        otherwise load it immediately.

        :return: The root of the tree.
        """
        if not self._root:
            self._root, self._annot = self._population._load(self._name)
        return self._root
