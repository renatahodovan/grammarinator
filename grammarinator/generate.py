# Copyright (c) 2017-2022 Renata Hodovan, Akos Kiss.
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
from contextlib import contextmanager
from functools import partial
from itertools import count
from math import inf
from multiprocessing import Manager, Pool
from os.path import abspath, basename, dirname, isdir, join, splitext
from shutil import rmtree

from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument
from inators.imp import import_object

from .cli import add_jobs_argument, init_logging, logger
from .pkgdata import __version__
from .runtime import CooldownModel, DefaultModel, Tree


class Population(object):

    def __init__(self, directory):
        self.directory = directory
        self.tree_extension = Tree.extension
        os.makedirs(directory, exist_ok=True)
        self.obj_list = glob.glob(join(self.directory, '*' + Tree.extension))

    def random_individuals(self, n=1):
        return random.sample(self.obj_list, n)

    def add_tree(self, fn):
        self.obj_list.append(fn)

    @property
    def size(self):
        return len(self.obj_list)


@contextmanager
def nullcontext():
    yield None


class Generator(object):

    def __init__(self, generator, rule, out_format,
                 model=None, listeners=None, max_depth=inf, cooldown=1.0,
                 population=None, generate=True, mutate=True, recombine=True, keep_trees=False,
                 transformers=None, serializer=None,
                 cleanup=True, encoding='utf-8'):

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

        if out_format and '%d' not in out_format:
            base, ext = splitext(out_format)
            self.out_format = '{base}%d{ext}'.format(base=base, ext=ext) if ext else join(base, '%d')
        else:
            self.out_format = out_format

        self.max_depth = float(max_depth)
        self.cooldown = float(cooldown)
        self.weights = {}
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
        if self.cleanup and self.out_format:
            rmtree(dirname(self.out_format))

    def __call__(self, index, *args, lock=None, **kwargs):
        lock = lock or nullcontext()
        return self.create_new_test(index, lock)[0]

    def create_new_test(self, index, lock):
        generators = []

        if self.enable_generation:
            generators.append(self.generate)

        if self.population:
            if self.enable_mutation and self.population.size > 0:
                generators.append(self.mutate)
            if self.enable_recombination and self.population.size > 1:
                generators.append(self.recombine)

        try:
            generator = random.choice(generators)
            tree = generator(self.rule, self.max_depth)
        except Exception as e:
            logger.warning('Test generation failed.', exc_info=e)
            return self.create_new_test(index, lock)

        test_fn = self.out_format % index if self.out_format else None
        tree.root = Generator.transform(tree.root, self.transformers)

        tree_fn = None
        if self.population and self.keep_trees:
            tree_fn = join(self.population.directory, basename(test_fn) + Tree.extension)
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
    def transform(root, transformers):
        for transformer in transformers:
            root = transformer(root)
        return root

    def generate(self, rule, max_depth):
        start_rule = getattr(self.generator_cls, rule)
        if not hasattr(start_rule, 'min_depth'):
            logger.warning('The \'min_depth\' property of %s is not set. Fallback to 0.', rule)
        elif start_rule.min_depth > max_depth:
            raise ValueError('{rule} cannot be generated within the given depth: {max_depth} (min needed: {depth}).'.format(rule=rule, max_depth=max_depth, depth=start_rule.min_depth))

        instances = {}

        def instantiate(cls):
            obj = instances.get(cls)
            if not obj:
                obj = cls()
                instances[cls] = obj
            return obj

        model = instantiate(self.model_cls)
        if self.cooldown < 1:
            model = CooldownModel(model, cooldown=self.cooldown, weights=self.weights)
        generator = self.generator_cls(model=model, max_depth=max_depth)
        for listener_cls in self.listener_cls:
            generator.listeners.append(instantiate(listener_cls))
        return Tree(getattr(generator, rule)())

    def random_individuals(self, n):
        return self.population.random_individuals(n=n)

    def mutate(self, *args):
        tree_fn = self.random_individuals(n=1)[0]
        tree = Tree.load(tree_fn)

        node = self.random_node(tree)
        if node is None:
            raise ValueError('Could not choose node to mutate.')

        new_tree = self.generate(node.name, self.max_depth - node.level)
        node.replace(new_tree.root)
        return tree

    def recombine(self, *args):
        tree_1_fn, tree_2_fn = self.random_individuals(n=2)
        tree_1 = Tree.load(tree_1_fn)
        tree_2 = Tree.load(tree_2_fn)

        common_types = set(tree_1.node_dict.keys()).intersection(set(tree_2.node_dict.keys()))
        options = self.default_selector(node for rule_name in common_types for node in tree_1.node_dict[rule_name])
        # Shuffle suitable nodes with sample.
        tree_1_iter = random.sample(options, k=len(options))
        for node_1 in tree_1_iter:
            for node_2 in random.sample(tree_2.node_dict[node_1.name], k=len(tree_2.node_dict[node_1.name])):
                # Make sure that the output tree won't exceed the depth limit.
                if node_1.level + node_2.depth <= self.max_depth:
                    node_1.replace(node_2)
                    return tree_1

        raise ValueError('Could not find node pairs to recombine.')

    def default_selector(self, iterable):
        def min_depth(node):
            return getattr(getattr(self.generator_cls, node.name), 'min_depth', 0)

        return [node for node in iterable if node.name is not None and node.parent is not None and node.name != 'EOF' and node.level + min_depth(node) < self.max_depth]

    def random_node(self, tree):
        options = self.default_selector(x for name in tree.node_dict for x in tree.node_dict[name])
        return random.choice(options) if options else None


def execute():
    def restricted_float(value):
        value = float(value)
        if value <= 0.0 or value > 1.0:
            raise ArgumentTypeError('{value!r} not in range (0.0, 1.0]'.format(value=value))
        return value

    parser = ArgumentParser(description='Grammarinator: Generate', epilog="""
        The tool acts as a default execution harness for generators
        created by Grammarinator:Processor.
        """)
    # Settings for generating from grammar.
    parser.add_argument('generator', metavar='NAME',
                        help='reference to the generator created by grammarinator-process (in package.module.class format).')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start generation from (default: first parser rule).')
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
                        help='initialize random number generator with fixed seed (not set by default; noneffective if parallelization is enabled).')
    add_jobs_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    if args.jobs == 1 and args.random_seed:
        random.seed(args.random_seed)

    init_logging()
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)

    if args.population:
        if not isdir(args.population):
            parser.error('Population must point to an existing directory.')
        args.population = abspath(args.population)

    with Generator(generator=args.generator, rule=args.rule, out_format=args.out,
                   model=args.model, listeners=args.listener, max_depth=args.max_depth, cooldown=args.cooldown,
                   population=args.population, generate=args.generate, mutate=args.mutate, recombine=args.recombine, keep_trees=args.keep_trees,
                   transformers=args.transformer, serializer=args.serializer,
                   cleanup=False, encoding=args.encoding) as generator:
        if args.jobs > 1:
            with Manager() if not args.out else nullcontext() as manager:
                if not args.out:
                    generator = partial(generator, lock=manager.Lock())  # pylint: disable=no-member
                with Pool(args.jobs) as pool:
                    for _ in pool.imap_unordered(generator, count(0) if args.n == inf else range(args.n)):
                        pass
        else:
            for i in count(0) if args.n == inf else range(args.n):
                generator(i)


if __name__ == '__main__':
    execute()
