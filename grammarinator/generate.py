# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import os

from argparse import ArgumentParser, ArgumentTypeError, SUPPRESS
from functools import partial
from itertools import count
from math import inf
from multiprocessing import Manager, Pool
from os.path import abspath, exists, isdir, join

from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument

from .cli import add_jobs_argument, init_logging, logger
from .pkgdata import __version__
from .tool import GeneratorTool


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

    with GeneratorTool(generator=args.generator, rule=args.rule, out_format=args.out,
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
