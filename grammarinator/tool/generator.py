# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import glob
import logging
import os
import random

from contextlib import nullcontext
from math import inf
from os.path import abspath, basename, dirname, join, splitext
from shutil import rmtree

from ..runtime import CooldownModel, CustomWeightsModel, DefaultModel, Tree

logger = logging.getLogger(__name__)


class Population(object):

    def __init__(self, directory):
        """
        :param str directory: Path to the directory containing the trees.
        """
        self.directory = directory
        self.tree_extension = Tree.extension
        os.makedirs(directory, exist_ok=True)
        self.obj_list = glob.glob(join(self.directory, '*' + Tree.extension))

    def random_individuals(self, n=1):
        """
        Select ``n`` items from the population.

        :param int n: Number of items to be selected.
        :return: List of selected tree paths.
        :rtype: list[str]
        """
        return random.sample(self.obj_list, n)

    def add_tree(self, fn):
        """
        Add a single tree to the popoulation by path.

        :param str fn: File path of tree to be added.
        """
        self.obj_list.append(fn)

    @property
    def size(self):
        """
        Number of trees in population.
        """
        return len(self.obj_list)


class DefaultGeneratorFactory(object):
    """
    The default generator factory implementation. Instances of
    ``DefaultGeneratorFactory`` are callable. When called, a new generator
    instance is created backed by a new decision model instance and a set of
    newly created listener objects is attached.
    """

    def __init__(self, generator_class, *,
                 model_class=None, custom_weights=None, cooldown=1.0, cooldown_weights=None, cooldown_lock=None,
                 listener_classes=None):
        """
        :param type[~grammarinator.runtime.Generator] generator_class: The class
            of the generator to instantiate.
        :param type model_class: The class of the model to instantiate. The
            model instance is used to instantiate the generator.
        :param dict[tuple,float] custom_weights: Weights assigned to
            alternatives. Used to instantiate a
            :class:`~grammarinator.runtime.CustomWeightsModel` wrapper around
            the model.
        :param float cooldown: Cooldown factor. Used to instantiate a
            :class:`~grammarinator.runtime.CooldownModel` wrapper around the
            model.
        :param dict[tuple,float] cooldown_weights: Cooldown weights of
            alternatives. Used to instantiate a
            :class:`~grammarinator.runtime.CooldownModel` wrapper around the
            model.
        :param multiprocessing.Lock cooldown_lock: Lock object when generating
            in parallel. Used to instantiate a
            :class:`~grammarinator.runtime.CooldownModel` wrapper around the
            model.
        :param list[type] listener_classes: List of listener classes to
            instantiate and attach to the generator.
        """
        self._generator_class = generator_class
        self._model_class = model_class or DefaultModel
        self._custom_weights = custom_weights
        self._cooldown = cooldown
        self._cooldown_weights = cooldown_weights
        self._cooldown_lock = cooldown_lock
        self._listener_classes = listener_classes or []

    def __call__(self, max_depth=inf):
        """
        Create a new generator instance according to the settings specified for
        the factory instance and for this method.

        :param int or float max_depth: Maximum tree depth to be generated
            (default: ``inf``). Used to instantiate the generator.
        :return: The created generator instance.
        :rtype: ~grammarinator.runtime.Generator
        """
        model = self._model_class()
        if self._custom_weights:
            model = CustomWeightsModel(model, self._custom_weights)
        if self._cooldown < 1:
            model = CooldownModel(model, cooldown=self._cooldown, weights=self._cooldown_weights, lock=self._cooldown_lock)

        generator = self._generator_class(model=model, max_depth=max_depth)

        for listener_class in self._listener_classes:
            generator.add_listener(listener_class())

        return generator

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError()
        return getattr(self._generator_class, name)


class GeneratorTool(object):
    """
    Class to create new test cases using the generator produced by ``grammarinator-process``.
    """

    def __init__(self, generator_factory, rule, out_format, lock=None, max_depth=inf,
                 population=None, generate=True, mutate=True, recombine=True, keep_trees=False,
                 transformers=None, serializer=None,
                 cleanup=True, encoding='utf-8'):
        """
        :param generator_factory: A callable that can produce instances of a
            generator. It is a generalization of a generator class: it has to
            instantiate a generator object, and it may also set the decision
            model and the listeners of the generator as well. In the simplest
            case, it can be a ``grammarinator-process``-created subclass of
            :class:`~grammarinator.runtime.Generator`, but in more complex
            scenarios a factory can be used, e.g., an instance of
            :class:`DefaultGeneratorFactory`.
        :param str rule: Name of the rule to start generation from.
        :param str out_format: Test output description. It can be a file path pattern possibly including the ``%d``
               placeholder which will be replaced by the index of the test case. Otherwise, it can be an empty string,
               which will result in printing the test case to the stdout (i.e., not saving to file system).
        :param multiprocessing.Lock lock: Lock object necessary when printing test cases in parallel (optional).
        :param int or float max_depth: Maximum recursion depth during generation (default: ``inf``).
        :param str population: Directory of grammarinator tree pool.
        :param bool generate: Enable generating new test cases from scratch, i.e., purely based on grammar.
        :param bool mutate: Enable mutating existing test cases, i.e., re-generate part of an existing test case based on grammar.
        :param bool recombine: Enable recombining existing test cases, i.e., replace part of a test case with a compatible part from another test case.
        :param bool keep_trees: Keep generated trees to participate in further mutations or recombinations
               (otherwise, only the initial population will be mutated or recombined). It has effect only if
               population is defined.
        :param list transformers: List of transformers to be applied to postprocess
               the generated tree before serializing it.
        :param serializer: A seralizer that takes a tree and produces a string from it (default: :class:`str`).
               See :func:`grammarinator.runtime.simple_space_serializer` for a simple solution that concatenates tokens with spaces.
        :param bool cleanup: Enable deleting the generated tests at :meth:`__exit__`.
        :param str encoding: Output file encoding.
        """

        self._generator_factory = generator_factory
        self._transformers = transformers or []
        self._serializer = serializer or str
        self._rule = rule

        if out_format:
            os.makedirs(abspath(dirname(out_format)), exist_ok=True)

        self._out_format = out_format
        self._lock = lock or nullcontext()
        self._max_depth = max_depth
        self._population = Population(population) if population else None
        self._enable_generation = generate
        self._enable_mutation = mutate
        self._enable_recombination = recombine
        self._keep_trees = keep_trees
        self._cleanup = cleanup
        self._encoding = encoding

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Delete the output directory if the tests were saved to files and if ``cleanup`` was enabled.
        """
        if self._cleanup and self._out_format:
            rmtree(dirname(self._out_format))

    def create(self, index):
        """
        Create new test case with a randomly selected generator method from the available
        options (i.e., via :meth:`generate`, :meth:`mutate`, or :meth:`recombine`). The
        generated tree is transformed, serialized and saved according to the parameters
        used to initialize the current generator object.

        :param int index: Index of the test case to be generated.
        :return: Tuple of the path to the generated serialized test file and the path to the tree file. The second item,
               (i.e., the path to the tree file) might be ``None``, if either ``population`` or ``keep_trees`` were not set
               in :meth:`__init__` and hence the tree object was not saved either.
        :rtype: tuple[str, str]
        """
        creators = []
        if self._enable_generation:
            creators.append(self.generate)
        if self._population:
            if self._enable_mutation and self._population.size > 0:
                creators.append(self.mutate)
            if self._enable_recombination and self._population.size > 1:
                creators.append(self.recombine)
        creator = random.choice(creators)

        tree = creator()
        for transformer in self._transformers:
            tree.root = transformer(tree.root)

        test_fn = self._out_format % index if '%d' in self._out_format else self._out_format
        tree_fn = None
        if self._population and self._keep_trees:
            tree_basename = basename(self._out_format)
            if '%d' not in tree_basename:
                base, ext = splitext(tree_basename)
                tree_basename = f'{base}%d{ext}'
            tree_fn = join(self._population.directory, tree_basename % index + Tree.extension)
            self._population.add_tree(tree_fn)
            tree.save(tree_fn)

        if test_fn:
            with codecs.open(test_fn, 'w', self._encoding) as f:
                f.write(self._serializer(tree.root))
        else:
            with self._lock:
                print(self._serializer(tree.root))

        return test_fn, tree_fn

    def generate(self, *, rule=None, max_depth=None):
        """
        Instantiate a new generator and generate a new tree from scratch.

        :param str rule: Name of the rule to start generation from.
        :param int max_depth: Maximum recursion depth during generation.
        :return: The generated tree.
        :rtype: Tree
        """
        max_depth = max_depth if max_depth is not None else self._max_depth
        generator = self._generator_factory(max_depth=max_depth)

        rule = rule or self._rule or generator._default_rule.__name__
        start_rule = getattr(generator, rule)
        if not hasattr(start_rule, 'min_depth'):
            logger.warning('The \'min_depth\' property of %s is not set. Fallback to 0.', rule)
        elif start_rule.min_depth > max_depth:
            raise ValueError(f'{rule} cannot be generated within the given depth: {max_depth} (min needed: {start_rule.min_depth}).')

        return Tree(start_rule())

    def mutate(self):
        """
        Select a tree randomly from the population and mutate it at a random position.

        :return: The mutated tree.
        :rtype: Tree
        """
        tree_fn = self._population.random_individuals(n=1)[0]
        tree = Tree.load(tree_fn)

        node = self._random_node(tree)
        if node is None:
            logger.debug('Could not choose node to mutate.')
            return tree

        new_tree = self.generate(rule=node.name, max_depth=self._max_depth - node.level)
        node.replace(new_tree.root)
        return tree

    def recombine(self):
        """
        Select two trees from the population and recombine them at a random
        position, where the nodes are compatible with each other (i.e., they
        share the same node name).

        :return: The recombined tree.
        :rtype: Tree
        """
        tree_1_fn, tree_2_fn = self._population.random_individuals(n=2)
        tree_1 = Tree.load(tree_1_fn)
        tree_2 = Tree.load(tree_2_fn)

        common_types = set(tree_1.node_dict.keys()).intersection(set(tree_2.node_dict.keys()))
        options = self._default_selector(node for rule_name in common_types for node in tree_1.node_dict[rule_name])
        # Shuffle suitable nodes with sample.
        tree_1_iter = random.sample(options, k=len(options))
        for node_1 in tree_1_iter:
            for node_2 in random.sample(tuple(tree_2.node_dict[node_1.name]), k=len(tree_2.node_dict[node_1.name])):
                # Make sure that the output tree won't exceed the depth limit.
                if node_1.level + node_2.depth <= self._max_depth:
                    node_1.replace(node_2)
                    return tree_1

        logger.debug('Could not find node pairs to recombine.')
        return tree_1

    # Filter items from ``nodes`` that can be regenerated within the current
    # maximum depth (except 'EOF' and '<INVALID>' nodes).
    def _default_selector(self, nodes):
        return [node for node in nodes if node.name is not None and node.parent is not None and node.name not in ['EOF', '<INVALID>'] and node.level + getattr(getattr(self._generator_factory, node.name), 'min_depth', 0) < self._max_depth]

    # Select a node randomly from ``tree`` which can be regenerated within
    # the current maximum depth.
    def _random_node(self, tree):
        options = self._default_selector(x for name in tree.node_dict for x in tree.node_dict[name])
        return random.choice(options) if options else None
