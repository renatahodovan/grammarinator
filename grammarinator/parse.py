# Copyright (c) 2018-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import os

from argparse import ArgumentParser
from math import inf
from multiprocessing import Pool
from os.path import exists, join

from antlerinator import add_antlr_argument, process_antlr_argument
from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument

from .cli import add_disable_cleanup_argument, add_jobs_argument, init_logging, logger
from .pkgdata import __version__
from .tool import ParserFactory


def iterate_tests(files, rule, out, encoding):
    for test in files:
        yield (test, rule, out, encoding)


def execute():
    parser = ArgumentParser(description='Grammarinator: Parser',
                            epilog="""
                            The tool parses files with ANTLR v4 grammars, builds Grammarinator-
                            compatible tree representations from them and saves them for further
                            reuse.
                            """)
    parser.add_argument('grammar', metavar='FILE', nargs='+',
                        help='ANTLR grammar files describing the expected format of input to parse.')
    parser.add_argument('-i', '--input', metavar='FILE', nargs='+', required=True,
                        help='input files to process.')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start parsing with (default: first parser rule).')
    parser.add_argument('-t', '--transformer', metavar='NAME', action='append', default=[],
                        help='reference to a transformer (in package.module.function format) to postprocess the parsed tree.')
    parser.add_argument('--hidden', metavar='NAME', action='append', default=[],
                        help='list of hidden tokens to be built into the parsed tree.')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='input file encoding (default: %(default)s).')
    parser.add_argument('--max-depth', type=int, default=inf,
                        help='maximum expected tree depth (deeper tests will be discarded (default: %(default)f)).')
    parser.add_argument('-o', '--out', metavar='DIR', default=os.getcwd(),
                        help='directory to save the trees (default: %(default)s).')
    parser.add_argument('--parser-dir', metavar='DIR',
                        help='directory to save the parser grammars (default: <OUTDIR>/grammars).')
    add_disable_cleanup_argument(parser)
    add_jobs_argument(parser)
    add_antlr_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    for grammar in args.grammar:
        if not exists(grammar):
            parser.error(f'{grammar} does not exist.')

    if not args.parser_dir:
        args.parser_dir = join(args.out, 'grammars')

    init_logging()
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)
    process_antlr_argument(args)

    with ParserFactory(grammars=args.grammar, hidden=args.hidden, transformers=args.transformer, parser_dir=args.parser_dir, antlr=args.antlr,
                       max_depth=args.max_depth, cleanup=args.cleanup) as factory:
        if args.jobs > 1:
            with Pool(args.jobs) as pool:
                pool.starmap(factory.tree_from_file, iterate_tests(args.input, args.rule, args.out, args.encoding))
        else:
            for create_args in iterate_tests(args.input, args.rule, args.out, args.encoding):
                factory.tree_from_file(*create_args)


if __name__ == '__main__':
    execute()
