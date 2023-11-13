# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import inspect
import json
import os
import random

from argparse import ArgumentParser, ArgumentTypeError, SUPPRESS
from functools import partial
from itertools import count
from math import inf
from multiprocessing import Manager, Pool
from os.path import abspath, exists, isdir, join

from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument
from inators.imp import import_object

from .cli import add_encoding_argument, add_encoding_errors_argument, add_jobs_argument, import_list, init_logging, logger
from .pkgdata import __version__
from .runtime import RuleSize
from .tool import DefaultGeneratorFactory, DefaultPopulation, GeneratorTool


def restricted_float(value):
    value = float(value)
    if value <= 0.0 or value > 1.0:
        raise ArgumentTypeError(f'{value!r} not in range (0.0, 1.0]')
    return value


def process_args(args):
    args.generator = import_object(args.generator)
    args.model = import_object(args.model)
    args.listener = import_list(args.listener)
    args.transformer = import_list(args.transformer)
    args.serializer = import_object(args.serializer) if args.serializer else None

    if args.weights:
        if not exists(args.weights):
            raise ValueError('Custom weights should point to an existing JSON file.')

        with open(args.weights, 'r') as f:
            weights = {}
            for rule, alts in json.load(f).items():
                for alternation_idx, alternatives in alts.items():
                    for alternative_idx, w in alternatives.items():
                        weights[(rule, int(alternation_idx), int(alternative_idx))] = w
            args.weights = weights
    else:
        args.weights = {}

    if args.population:
        if not isdir(args.population):
            raise ValueError('Population must point to an existing directory.')
        args.population = abspath(args.population)


def generator_tool_helper(args, weights, lock):
    return GeneratorTool(generator_factory=DefaultGeneratorFactory(args.generator,
                                                                   model_class=args.model,
                                                                   cooldown=args.cooldown,
                                                                   weights=weights,
                                                                   lock=lock,
                                                                   listener_classes=args.listener),
                         rule=args.rule, out_format=args.out,
                         limit=RuleSize(depth=args.max_depth, tokens=args.max_tokens),
                         population=DefaultPopulation(args.population,
                                                      min_sizes={name: method.min_size
                                                                 for name, method in inspect.getmembers(args.generator, inspect.ismethod)
                                                                 if hasattr(method, 'min_size')},
                                                      immutable_rules=args.generator._immutable_rules) if args.population else None,
                         generate=args.generate, mutate=args.mutate, recombine=args.recombine, keep_trees=args.keep_trees,
                         transformers=args.transformer, serializer=args.serializer,
                         cleanup=False, encoding=args.encoding, errors=args.encoding_errors, dry_run=args.dry_run)


def create_test(generator_tool, index, *, seed):
    if seed:
        random.seed(seed + index)
    return generator_tool.create(index)


def execute():
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
    parser.add_argument('--max-tokens', default=inf, type=int, metavar='NUM',
                        help='maximum token number during generation (default: %(default)f).')
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
    parser.add_argument('--stdout', dest='out', action='store_const', const='', default=SUPPRESS,
                        help='print test cases to stdout (alias for --out=%(const)r)')
    parser.add_argument('-n', default=1, type=int, metavar='NUM',
                        help='number of tests to generate, \'inf\' for continuous generation (default: %(default)s).')
    parser.add_argument('--random-seed', type=int, metavar='NUM',
                        help='initialize random number generator with fixed seed (not set by default).')
    parser.add_argument('--dry-run', default=False, action='store_true',
                        help='generate tests without writing them to file or printing to stdout (do not keep generated tests in population either)')
    add_encoding_argument(parser, help='output file encoding (default: %(default)s).')
    add_encoding_errors_argument(parser)
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
    try:
        process_args(args)
    except ValueError as e:
        parser.error(e)

    if args.jobs > 1:
        with Manager() as manager:
            with generator_tool_helper(args, weights=manager.dict(args.weights), lock=manager.Lock()) as generator_tool:  # pylint: disable=no-member
                parallel_create_test = partial(create_test, generator_tool, seed=args.random_seed)
                with Pool(args.jobs) as pool:
                    for _ in pool.imap_unordered(parallel_create_test, count(0) if args.n == inf else range(args.n)):
                        pass
    else:
        with generator_tool_helper(args, weights=args.weights, lock=None) as generator_tool:
            for i in count(0) if args.n == inf else range(args.n):
                create_test(generator_tool, i, seed=args.random_seed)


if __name__ == '__main__':
    execute()
