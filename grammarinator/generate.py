# Copyright (c) 2017-2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import glob
import importlib
import json
import logging
import random
import uuid
import sys

import os
from os.path import abspath, basename, dirname, isdir, join, splitext

from argparse import ArgumentParser, ArgumentTypeError
from shutil import rmtree

from .pkgdata import __version__
from .runtime import Tree

logger = logging.getLogger('grammarinator')
logging.basicConfig(format='%(message)s')


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


class Generator(object):

    def __init__(self, unlexer_path, unparser_path, rule, out_format, max_depth=float('inf'), cooldown=1.0,
                 population=None, generate=True, mutate=True, recombine=True, keep_trees=False,
                 tree_transformers=None, test_transformers=None,
                 cleanup=True, encoding='utf-8'):

        def import_entity(name):
            steps = name.split('.')
            return getattr(importlib.import_module('.'.join(steps[0:-1])), steps[-1])

        def get_boolean(value):
            return value in ['True', True, 1]

        if dirname(unlexer_path) not in sys.path:
            sys.path.append(dirname(unparser_path))

        if dirname(unparser_path) not in sys.path:
            sys.path.append(dirname(unparser_path))

        unlexer, unparser = splitext(basename(unlexer_path))[0], splitext(basename(unparser_path))[0]
        self.unlexer_cls = import_entity('.'.join([unlexer, unlexer]))
        self.unlexer_kwargs = dict(cooldown=float(cooldown), weights=dict())
        self.unparser_cls = import_entity('.'.join([unparser, unparser]))
        self.rule = rule or self.unparser_cls.default_rule.__name__

        out_dir = abspath(dirname(out_format))
        os.makedirs(out_dir, exist_ok=True)

        if '%d' not in out_format:
            base, ext = splitext(out_format)
            self.out_format = '{base}%d{ext}'.format(base=base, ext=ext) if ext else join(base, '%d')
        else:
            self.out_format = out_format

        self.max_depth = float(max_depth)
        self.cooldown = float(cooldown)
        self.population = Population(population) if population else None
        self.enable_generation = get_boolean(generate)
        self.enable_mutation = get_boolean(mutate)
        self.enable_recombination = get_boolean(recombine)
        self.keep_trees = get_boolean(keep_trees)
        self.cleanup = get_boolean(cleanup)
        self.encoding = encoding

        tree_transformers = tree_transformers or []
        if isinstance(tree_transformers, str):
            tree_transformers = json.loads(tree_transformers)
        self.tree_transformers = [import_entity(transformer) for transformer in tree_transformers]

        test_transformers = test_transformers or []
        if isinstance(test_transformers, str):
            test_transformers = json.loads(test_transformers)
        self.test_transformers = [import_entity(transformer) for transformer in test_transformers]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cleanup:
            rmtree(dirname(self.out_format))

    def __call__(self, *args, **kwargs):
        return self.create_new_test()[0]

    def create_new_test(self):
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
            logger.warning('Test generation failed: %s.', e)
            return self.create_new_test()

        # Ensure creating unique tests even if the output directory is not empty.
        test_fn = self.out_format % uuid.uuid4().int
        tree.root = Generator.transform(tree.root, self.tree_transformers)

        tree_fn = None
        if self.keep_trees:
            tree_fn = join(self.population.directory, basename(test_fn) + Tree.extension)
            self.population.add_tree(tree_fn)
            tree.save(tree_fn)

        with codecs.open(test_fn, 'w', self.encoding) as f:
            f.write(str(Generator.transform(tree.root, self.test_transformers)))

        return test_fn, tree_fn

    def serialize(self, tree):
        tree.root = Generator.transform(tree.root, self.tree_transformers)
        tree.root = Generator.transform(tree.root, self.test_transformers)
        return str(tree.root)

    @staticmethod
    def transform(root, transformers):
        for transformer in transformers:
            root = transformer(root)
        return root

    def generate(self, rule, max_depth):
        start_rule = getattr(self.unparser_cls if rule[0].islower() else self.unlexer_cls, rule)
        if not hasattr(start_rule, 'min_depth'):
            logger.warning('The \'min_depth\' property of %s is not set. Fallback to 0.', rule)
        elif start_rule.min_depth > max_depth:
            raise ValueError('{rule} cannot be generated within the given depth: {max_depth} (min needed: {depth}).'.format(rule=rule, max_depth=max_depth, depth=start_rule.min_depth))

        unlexer = self.unlexer_cls(**dict(self.unlexer_kwargs, max_depth=max_depth))
        tree = Tree(getattr(self.unparser_cls(unlexer) if rule[0].islower() else unlexer, rule)())
        return tree

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
        options = self.default_selector([node for rule_name in common_types for node in tree_1.node_dict[rule_name]])
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
        return [node for node in iterable if node.name is not None and node.parent is not None and node.name != 'EOF' and node.level < self.max_depth]

    def random_node(self, tree):
        options = self.default_selector([x for name in tree.node_dict for x in tree.node_dict[name]])
        return random.choice(options) if options else None


def execute():
    def restricted_float(value):
        value = float(value)
        if value <= 0.0 or value > 1.0:
            raise ArgumentTypeError('{value!r} not in range (0.0, 1.0]'.format(value=value))
        return value

    parser = ArgumentParser(description='Grammarinator: Generate', epilog="""
        The tool acts as a default execution harness for unlexers and unparsers
        created by Grammarinator:Processor.
        """)
    # Settings for generating from grammar.
    parser.add_argument('-p', '--unparser', required=True, metavar='FILE',
                        help='grammarinator-generated unparser.')
    parser.add_argument('-l', '--unlexer', required=True, metavar='FILE',
                        help='grammarinator-generated unlexer.')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start generation from (default: first parser rule).')
    parser.add_argument('-t', '--tree-transformers', metavar='LIST', nargs='+', default=[],
                        help='list of transformers (in package.module.function format) to postprocess the generated tree '
                             '(the result of these transformers will be saved into the serialized tree, e.g., variable matching).')
    parser.add_argument('--test-transformers', metavar='LIST', nargs='+', default=[],
                        help='list of transformers (in package.module.function format) to postprocess the generated tree '
                             '(the result of these transformers will only affect test serialization but won\'t be saved to the '
                             'tree representation, e.g., space insertion).')
    parser.add_argument('-d', '--max-depth', default=float('inf'), type=int, metavar='NUM',
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
                        help='keep generated tests to participate in further mutations or recombinations (default: %(default)d).')

    # Auxiliary settings.
    parser.add_argument('-j', '--jobs', default=os.cpu_count(), type=int, metavar='NUM',
                        help='test generation parallelization level (default: number of cpu cores (%(default)d)).')
    parser.add_argument('-o', '--out', metavar='FILE', default=join(os.getcwd(), 'tests', 'test_%d'),
                        help='output file name pattern (default: %(default)s).')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='output file encoding (default: %(default)s).')
    parser.add_argument('--log-level', default='INFO', metavar='LEVEL',
                        help='verbosity level of diagnostic messages (default: %(default)s).')
    parser.add_argument('-n', default=1, type=int, metavar='NUM',
                        help='number of tests to generate (default: %(default)s).')
    parser.add_argument('--sys-recursion-limit', metavar='NUM', type=int, default=sys.getrecursionlimit(),
                        help='override maximum depth of the Python interpreter stack')
    parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))
    args = parser.parse_args()

    logger.setLevel(args.log_level)
    sys.setrecursionlimit(args.sys_recursion_limit)

    if args.population:
        if not isdir(args.population):
            parser.error('Population must point to an existing directory.')
        args.population = abspath(args.population)

    with Generator(unlexer_path=args.unlexer, unparser_path=args.unparser, rule=args.rule, out_format=args.out,
                   max_depth=args.max_depth, cooldown=args.cooldown,
                   population=args.population, generate=args.generate, mutate=args.mutate, recombine=args.recombine, keep_trees=args.keep_trees,
                   tree_transformers=args.tree_transformers, test_transformers=args.test_transformers,
                   cleanup=False, encoding=args.encoding) as generator:
        for i in range(args.n):
            test_fn = generator()
            logger.debug('#%s %s', i, test_fn)


if __name__ == '__main__':
    execute()
