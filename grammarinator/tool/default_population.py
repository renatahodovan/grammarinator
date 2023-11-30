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

from ..runtime import Population, Rule
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

    def __bool__(self):
        """
        Check whether there is at least a single individual in the population.
        """
        return len(self._files) > 0

    def add_individual(self, root, annotations=None, path=None):
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
        with open(fn, 'wb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                f.write(self._codec.encode_annotated(root, annotations))
            else:
                f.write(self._codec.encode(root))
        self._files.append(fn)

    def select_individual(self):
        """
        Randomly select an individual of the population.
        """
        fn = random.sample(self._files, k=1)[0]
        with open(fn, 'rb') as f:
            if isinstance(self._codec, AnnotatedTreeCodec):
                root, annot = self._codec.decode_annotated(f.read())
            else:
                root, annot = self._codec.decode(f.read()), None
            assert isinstance(root, Rule), root
        return root, annot
