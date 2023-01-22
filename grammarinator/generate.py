# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import glob
import json
import os
import random

from argparse import ArgumentParser, ArgumentTypeError, SUPPRESS
from contextlib import nullcontext
from functools import partial
from itertools import count
from math import inf
from multiprocessing import Manager, Pool
from os.path import abspath, basename, dirname, exists, isdir, join, splitext
from shutil import rmtree

from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument
from inators.imp import import_object

from .cli import add_jobs_argument, init_logging, logger
from .pkgdata import __version__
from .runtime import CooldownModel, CustomWeightsModel, DefaultModel, Tree


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


def execute():
    def restricted_float(value):
        value = float(value)
        if value <= 0.0 or value > 1.0:
            raise ArgumentTypeError(f'{value!r} not in range (0.0, 1.0]')
        return value

    def convert_weights(dct):
        weights = {}
        for rule, alts in dct.items():
            for alternation_idx, alternatives in alts.items():
                for alternative_idx, w in alternatives.items():
                    weights[(rule, int(alternation_idx), int(alternative_idx))] = w
        return weights

    parser = ArgumentParser(description='Grammarinator: Generate', epilog="""
        The tool acts as a default execution harness for generators
        created by Grammarinator:Processor.
        """)
    # Settings for generating from grammar.
    parser.add_argument('generator', metavar='NAME',
                        help='reference to the generator created by grammarinator-process (in package.module.class format).')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start generation from (default: the parser rule set by grammarinator-process).')
    parser.add_argument('-m', '--model', metavar='NAME', default='grammarinator.runtime.DefaultModel',
                        help='reference to the decision model (in package.module.class format) (default: %(default)s).')
    parser.add_argument('-l', '--listener', metavar='NAME', action='append', default=[],
                        help='reference to a listener (in package.module.class format).')
    parser.add_argument('-t', '--transformer', metavar='NAME', action='append', default=[],
                        help='reference to a transformer (in package.module.function format) to postprocess the generated tree '
                             '(the result of these transformers will be saved into the serialized tree, e.g., variable matching).')
    parser.add_argument('-s', '--serializer', metavar='NAME',
                        help='reference to a seralizer (in package.module.function format) that takes a tree and produces a string from it.')
    parser.add_argument('-d', '--max-depth', default=inf, type=int, metavar='NUM',
                        help='maximum recursion depth during generation (default: %(default)f).')
    parser.add_argument('-c', '--cooldown', default=1.0, type=restricted_float, metavar='NUM',
                        help='cool-down factor defines how much the probability of an alternative should decrease '
                             'after it has been chosen (interval: (0, 1]; default: %(default)f).')
    parser.add_argument('-w', '--weights', metavar='FILE',
                        help='JSON file defining custom weights for alternatives.')

    # Evolutionary settings.
    parser.add_argument('--population', metavar='DIR',
                        help='directory of grammarinator tree pool.')
    parser.add_argument('--no-generate', dest='generate', default=True, action='store_false',
                        help='disable test generation from grammar.')
    parser.add_argument('--no-mutate', dest='mutate', default=True, action='store_false',
                        help='disable test generation by mutation (disabled by default if no population is given).')
    parser.add_argument('--no-recombine', dest='recombine', default=True, action='store_false',
                        help='disable test generation by recombination (disabled by default if no population is given).')
    parser.add_argument('--keep-trees', default=False, action='store_true',
                        help='keep generated tests to participate in further mutations or recombinations (only if population is given).')

    # Auxiliary settings.
    parser.add_argument('-o', '--out', metavar='FILE', default=join(os.getcwd(), 'tests', 'test_%d'),
                        help='output file name pattern (default: %(default)s).')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='output file encoding (default: %(default)s).')
    parser.add_argument('--stdout', dest='out', action='store_const', const='', default=SUPPRESS,
                        help='print test cases to stdout (alias for --out=%(const)r)')
    parser.add_argument('-n', default=1, type=int, metavar='NUM',
                        help='number of tests to generate, \'inf\' for continuous generation (default: %(default)s).')
    parser.add_argument('--random-seed', type=int, metavar='NUM',
                        help='initialize random number generator with fixed seed (not set by default).')
    add_jobs_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    init_logging()
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)

    if args.weights:
        if not exists(args.weights):
            parser.error('Custom weights should point to an existing JSON file.')
        with open(args.weights, 'r') as f:
            args.weights = convert_weights(json.load(f))

    if args.population:
        if not isdir(args.population):
            parser.error('Population must point to an existing directory.')
        args.population = abspath(args.population)

    with Generator(generator=args.generator, rule=args.rule, out_format=args.out,
                   model=args.model, listeners=args.listener, max_depth=args.max_depth, cooldown=args.cooldown, weights=args.weights,
                   population=args.population, generate=args.generate, mutate=args.mutate, recombine=args.recombine, keep_trees=args.keep_trees,
                   transformers=args.transformer, serializer=args.serializer,
                   cleanup=False, encoding=args.encoding) as generator:
        if args.jobs > 1:
            with Manager() as manager:
                generator = partial(generator, seed=args.random_seed, weights=manager.dict(), lock=manager.Lock())  # pylint: disable=no-member
                with Pool(args.jobs) as pool:
                    for _ in pool.imap_unordered(generator, count(0) if args.n == inf else range(args.n)):
                        pass
        else:
            weights = {}
            for i in count(0) if args.n == inf else range(args.n):
                generator(i, seed=args.random_seed, weights=weights)


if __name__ == '__main__':
    execute()
