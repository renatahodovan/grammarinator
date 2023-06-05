# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import glob
import json
import logging
import os
import random

from contextlib import nullcontext
from math import inf
from os.path import abspath, basename, dirname, join, splitext
from shutil import rmtree

from inators.imp import import_object

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


class Generator(object):
    """
    Class to create new test cases using the generator produced by ``grammarinator-process``.
    Its interface follows the expectation of the Fuzzinator fuzzer framework.
    """

    def __init__(self, generator, rule, out_format,
                 model=None, listeners=None, max_depth=inf, cooldown=1.0, weights=None,
                 population=None, generate=True, mutate=True, recombine=True, keep_trees=False,
                 transformers=None, serializer=None,
                 cleanup=True, encoding='utf-8'):
        """
        :param str generator: Reference to the generator created by ``grammarinator-process`` (in package.module.class format).
        :param str rule: Name of the rule to start generation from.
        :param str out_format: Test output description. It can be a file path pattern possibly including the ``%d``
               placeholder which will be replaced by the index of the test case. Otherwise, it can be an empty string,
               which will result in printing the test case to the stdout (i.e., not saving to file system).
        :param str model: Reference to the decision model (in package.module.class format).
               See :class:`grammarinator.runtime.DefaultModel` for the default unguided random model.
        :param str or list[str] listeners: References to listeners to be applied (in package.module.class format).
               If it is a list, then each element should be a reference to a listener. If it is a string, then it
               should be a JSON-formatted list of references.
               See :class:`grammarinator.runtime.DefaultListener` for the default listener.
        :param int or float max_depth: Maximum recursion depth during generation (default: ``inf``).
        :param float cooldown: Defines how much the probability of an alternative should decrease after it has been chosen.
               See :class:`grammarinator.runtime.CooldownModel` for details.
               (default: 1.0, meaning no decrease in the probability).
        :param dict[tuple,float] weights: Weights assigned to alternatives. Any alternative that has no weight assigned is
               treated as if 1.0 were assigned.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of
               :meth:`grammarinator.runtime.DefaultModel.choice`, while the third element corresponds to the indices of
               its ``weights`` parameter. See :class:`grammarinator.runtime.CustomWeightsModel`.
        :param str population: Directory of grammarinator tree pool.
        :param bool generate: Enable generating new test cases from scratch, i.e., purely based on grammar.
        :param bool mutate: Enable mutating existing test cases, i.e., re-generate part of an existing test case based on grammar.
        :param bool recombine: Enable recombining existing test cases, i.e., replace part of a test case with a compatible part from another test case.
        :param bool keep_trees: Keep generated trees to participate in further mutations or recombinations
               (otherwise, only the initial population will be mutated or recombined). It has effect only if
               population is defined.
        :param str or list[str] transformers: References to transformers to be applied to postprocess
               the generated tree before serializing it. If it is a list, then each element should be a
               reference to a transformer. If it is a string, then it should be a JSON-formatted list of
               references. The references should be in package.module.function format.
        :param str serializer: Reference to a seralizer (in package.module.function format) that takes a tree and produces a string from it.
               See :func:`grammarinator.runtime.simple_space_serializer` for a simple solution that concatenates tokens with spaces.
        :param bool cleanup: Enable deleting the generated tests at :meth:`__exit__`.
        :param str encoding: Output file encoding.
        """

        def import_list(lst):
            lst = lst or []
            if isinstance(lst, str):
                lst = json.loads(lst)
            return [import_object(item) for item in lst]

        def get_boolean(value):
            return value in ['True', True, 1]

        self.generator_cls = import_object(generator) if generator else None
        self.model_cls = import_object(model) if model else DefaultModel
        self.listener_cls = import_list(listeners)
        self.transformers = import_list(transformers)
        self.serializer = import_object(serializer) if serializer else str
        self.rule = rule or self.generator_cls._default_rule.__name__

        if out_format:
            os.makedirs(abspath(dirname(out_format)), exist_ok=True)

        self.out_format = out_format
        self.max_depth = float(max_depth)
        self.cooldown = float(cooldown)
        self.weights = weights
        self.population = Population(population) if population else None
        self.enable_generation = get_boolean(generate)
        self.enable_mutation = get_boolean(mutate)
        self.enable_recombination = get_boolean(recombine)
        self.keep_trees = get_boolean(keep_trees)
        self.cleanup = get_boolean(cleanup)
        self.encoding = encoding

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Delete the output directory if the tests were saved to files and if ``cleanup`` was enabled.
        """
        if self.cleanup and self.out_format:
            rmtree(dirname(self.out_format))

    def __call__(self, index, *args, seed=None, weights=None, lock=None, **kwargs):
        """
        Trampoline to :meth:`create_new_test`. This trampoline is needed to implement the
        :class:`fuzzinator.fuzzer.Fuzzer` interface expectation of Fuzzinator (having only an index parameter).

        :param int index: Index of the test case to be generated.
        :param int seed: Seed of the random number generator to ensure reproducible results (optional).
        :param dict[tuple,float] weights: Cooldown weights of alternatives calculated by
               :class:`grammarinator.runtime.CooldownModel`, if it is applied. It is only useful, if the same
               dictionary object is passed to every invocation of this method so that the decisions made
               during test case generation can affect those that follow.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of
               :meth:`grammarinator.runtime.CooldownModel.choice`, while the third element corresponds to the indices of
               its ``weights`` parameter.
        :param multiprocessing.Lock lock: Lock object when generating in parallel (optional).
        :return: Path of the output test.
        :rtype: str
        """
        if seed:
            random.seed(seed + index)
        weights = weights if weights is not None else {}
        lock = lock or nullcontext()
        return self.create_new_test(index, weights, lock)[0]

    def create_new_test(self, index, weights, lock):
        """
        Create new test case with a randomly selected generator method from the available
        options (i.e., via :meth:`generate`, :meth:`mutate`, or :meth:`recombine`). The
        generated tree is transformed, serialized and saved according to the parameters
        used to initialize the current generator object.

        :param int index: Index of the test case to be generated.
        :param dict[tuple,float] weights: Cooldown weights of alternatives calculated by
               :class:`grammarinator.runtime.CooldownModel`, if it is applied. It is only useful, if the same
               dictionary object is passed to every invocation of this method so that the decisions made
               during test case generation can affect those that follow.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of
               :meth:`grammarinator.runtime.DefaultModel.choice`, while the third element corresponds to the indices of
               its ``weights`` parameter.
        :param multiprocessing.Lock lock: Lock object when generating in parallel (optional).
        :return: Tuple of the path to the generated serialized test file and the path to the tree file. The second item,
               (i.e., the path to the tree file) might be ``None``, if either ``population`` or ``keep_trees`` were not set
               in :meth:`__init__` and hence the tree object was not saved either.
        :rtype: tuple[str, str]
        """
        generators = []

        if self.enable_generation:
            generators.append(self.generate)

        if self.population:
            if self.enable_mutation and self.population.size > 0:
                generators.append(self.mutate)
            if self.enable_recombination and self.population.size > 1:
                generators.append(self.recombine)

        generator = random.choice(generators)
        tree = generator(rule=self.rule, max_depth=self.max_depth, weights=weights, lock=lock)
        test_fn = self.out_format % index if '%d' in self.out_format else self.out_format
        tree.root = Generator._transform(tree.root, self.transformers)

        tree_fn = None
        if self.population and self.keep_trees:
            tree_basename = basename(self.out_format)
            if '%d' not in tree_basename:
                base, ext = splitext(tree_basename)
                tree_basename = f'{base}%d{ext}'
            tree_fn = join(self.population.directory, tree_basename % index + Tree.extension)
            self.population.add_tree(tree_fn)
            tree.save(tree_fn)

        if test_fn:
            with codecs.open(test_fn, 'w', self.encoding) as f:
                f.write(self.serializer(tree.root))
        else:
            with lock:
                print(self.serializer(tree.root))

        return test_fn, tree_fn

    @staticmethod
    def _transform(root, transformers):
        for transformer in transformers:
            root = transformer(root)
        return root

    def generate(self, *, rule, max_depth, weights, lock):
        """
        Instantiate a new generator and generate a new tree from scratch.

        :param str rule: Name of the rule to start generation from.
        :param int max_depth: Maximum recursion depth during generation.
        :param dict[tuple,float] weights: Cooldown weights of alternatives calculated by
               :class:`grammarinator.runtime.CooldownModel`, if it is applied. It is only useful, if the same
               dictionary object is passed to every invocation of this method so that the decisions made
               during test case generation can affect those that follow.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of
               :meth:`grammarinator.runtime.DefaultModel.choice`, while the third element corresponds to the indices of
               its ``weights`` parameter.
        :param multiprocessing.Lock lock: Lock object when generating in parallel (optional).
        :return: The generated tree.
        :rtype: Tree
        """
        start_rule = getattr(self.generator_cls, rule)
        if not hasattr(start_rule, 'min_depth'):
            logger.warning('The \'min_depth\' property of %s is not set. Fallback to 0.', rule)
        elif start_rule.min_depth > max_depth:
            raise ValueError(f'{rule} cannot be generated within the given depth: {max_depth} (min needed: {start_rule.min_depth}).')

        instances = {}

        def instantiate(cls):
            obj = instances.get(cls)
            if not obj:
                obj = cls()
                instances[cls] = obj
            return obj

        model = instantiate(self.model_cls)
        if self.weights:
            model = CustomWeightsModel(model, self.weights)
        if self.cooldown < 1:
            model = CooldownModel(model, cooldown=self.cooldown, weights=weights, lock=lock)
        generator = self.generator_cls(model=model, max_depth=max_depth)
        for listener_cls in self.listener_cls:
            generator.add_listener(instantiate(listener_cls))
        return Tree(getattr(generator, rule)())

    def _random_individuals(self, n):
        return self.population.random_individuals(n=n)

    def mutate(self, *, weights, lock, **kwargs):
        """
        Select a tree randomly from the population and mutate it at a random position.

        :param dict[tuple,float] weights: Cooldown weights of alternatives calculated by
               :class:`grammarinator.runtime.CooldownModel`, if it is applied. It is only useful, if the same
               dictionary object is passed to every invocation of this method so that the decisions made
               during test case generation can affect those that follow.
               The keys of the dictionary are tuples in the form of ``(str, int, int)``, each denoting an alternative:
               the first element specifies the name of the rule that contains the alternative, the second element
               specifies the index of the alternation containing the alternative within the rule, and the third element
               specifies the index of the alternative within the alternation (both indices start counting from 0). The
               first and second elements correspond to the ``node`` and ``idx`` parameters of
               :meth:`grammarinator.runtime.DefaultModel.choice`, while the third element corresponds to the indices of
               its ``weights`` parameter.
        :param multiprocessing.Lock lock: Lock object when generating in parallel (optional).
        :return: The mutated tree.
        :rtype: Tree
        """
        tree_fn = self._random_individuals(n=1)[0]
        tree = Tree.load(tree_fn)

        node = self._random_node(tree)
        if node is None:
            logger.debug('Could not choose node to mutate.')
            return tree

        new_tree = self.generate(rule=node.name, max_depth=self.max_depth - node.level, weights=weights, lock=lock)
        node.replace(new_tree.root)
        return tree

    def recombine(self, **kwargs):
        """
        Select two trees from the population and recombine them at a random
        position, where the nodes are compatible with each other (i.e., they
        share the same node name).

        :return: The recombined tree.
        :rtype: Tree
        """
        tree_1_fn, tree_2_fn = self._random_individuals(n=2)
        tree_1 = Tree.load(tree_1_fn)
        tree_2 = Tree.load(tree_2_fn)

        common_types = set(tree_1.node_dict.keys()).intersection(set(tree_2.node_dict.keys()))
        options = self._default_selector(node for rule_name in common_types for node in tree_1.node_dict[rule_name])
        # Shuffle suitable nodes with sample.
        tree_1_iter = random.sample(options, k=len(options))
        for node_1 in tree_1_iter:
            for node_2 in random.sample(tuple(tree_2.node_dict[node_1.name]), k=len(tree_2.node_dict[node_1.name])):
                # Make sure that the output tree won't exceed the depth limit.
                if node_1.level + node_2.depth <= self.max_depth:
                    node_1.replace(node_2)
                    return tree_1

        logger.debug('Could not find node pairs to recombine.')
        return tree_1

    # Filter items from ``nodes`` that can be regenerated within the current
    # maximum depth (except 'EOF' and '<INVALID>' nodes).
    def _default_selector(self, nodes):
        def min_depth(node):
            return getattr(getattr(self.generator_cls, node.name), 'min_depth', 0)

        return [node for node in nodes if node.name is not None and node.parent is not None and node.name not in ['EOF', '<INVALID>'] and node.level + min_depth(node) < self.max_depth]

    # Select a node randomly from ``tree`` which can be regenerated within
    # the current maximum depth.
    def _random_node(self, tree):
        options = self._default_selector(x for name in tree.node_dict for x in tree.node_dict[name])
        return random.choice(options) if options else None
