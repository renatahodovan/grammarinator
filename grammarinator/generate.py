# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import importlib
import logging
import pkgutil
import sys

from argparse import ArgumentParser
from multiprocessing import Pool
from os import cpu_count, getcwd, makedirs
from os.path import basename, dirname, exists, join, splitext

from .pkgdata import __version__

logger = logging.getLogger('grammarinator')
logging.basicConfig(format='%(message)s')


def generate(lexer_cls, parser_cls, rule, max_depth, transformers, out):
    parser = parser_cls(lexer_cls())
    if parser.min_depths[rule] > max_depth:
        logger.warning('{rule} cannot be generated within the given depth (min needed: {cnt}).'.format(rule=rule, cnt=parser.min_depths[rule]))
        return

    root = getattr(parser, rule)(max_depth=max_depth)
    for transformer in transformers:
        root = transformer(root)

    with open(out, 'w') as f:
        f.write(str(root))


def import_entity(name):
    steps = name.split('.')
    module_name = '.'.join(steps[0:-1])
    entity_name = steps[-1]
    module = importlib.import_module(module_name)
    return eval('module.' + entity_name)


def execute():
    parser = ArgumentParser(description='Grammarinator: Generate')
    parser.add_argument('-p', '--unparser', required=True, metavar='FILE',
                        help='grammarinator-generated unparser.')
    parser.add_argument('-l', '--unlexer', required=True, metavar='FILE',
                        help='grammarinator-generated unlexer.')
    parser.add_argument('-r', '--rule', required=True, metavar='NAME',
                        help='name of the rule to start generation from.')
    parser.add_argument('-t', '--transformers', metavar='LIST', nargs='+', default=[],
                        help='list of transformators (in package.module.function format) to postprocess the generated tree.')
    parser.add_argument('-d', '--max-depth', default=float('inf'), type=int, metavar='NUM',
                        help='maximum recursion depth during generation (default: %(default)f).')
    parser.add_argument('-j', '--jobs', default=cpu_count(), type=int, metavar='NUM',
                        help='test generation parallelization level (default: number of cpu cores (%(default)d)).')
    parser.add_argument('-o', '--out', metavar='FILE', default=join(getcwd(), 'test_%d'),
                        help='output file format (default: %(default)s).')
    parser.add_argument('--log-level', default=logging.INFO, metavar='LEVEL',
                        help='verbosity level of diagnostic messages (default: %(default)s).')
    parser.add_argument('-n', default=1, type=int, metavar='NUM',
                        help='number of tests to generate.')
    parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))
    args = parser.parse_args()

    logger.setLevel(args.log_level)

    out_dir = dirname(args.out)
    if not exists(out_dir):
        makedirs(out_dir, exist_ok=True)

    if '%d' not in args.out:
        base, ext = splitext(args.out)
        args.out = '{base}%d{ext}'.format(base=base, ext=ext) if ext else join(base, '%d')

    sys.path.append(dirname(args.unparser))
    unlexer = splitext(basename(args.unlexer))[0]
    unparser = splitext(basename(args.unparser))[0]

    lexer_cls = import_entity('.'.join([unlexer, unlexer]))
    parser_cls = import_entity('.'.join([unparser, unparser]))
    transformers = [import_entity(transformer) for transformer in args.transformers]

    if args.jobs > 1:
        with Pool(args.jobs) as pool:
            pool.starmap(generate, [(lexer_cls, parser_cls, args.rule, args.max_depth, transformers, args.out % i) for i in range(args.n)])
    else:
        for i in range(args.n):
            generate(lexer_cls, parser_cls, args.rule, args.max_depth, transformers, args.out % i)


if __name__ == '__main__':
    execute()
