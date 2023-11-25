# Copyright (c) 2018-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import os

from argparse import ArgumentParser
from multiprocessing import Pool
from os.path import exists, join

from antlerinator import add_antlr_argument, process_antlr_argument
from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument

from .cli import add_disable_cleanup_argument, add_encoding_argument, add_encoding_errors_argument, add_tree_format_argument, add_jobs_argument, import_list, init_logging, logger, process_tree_format_argument
from .pkgdata import __version__
from .runtime import RuleSize
from .tool import DefaultPopulation, ParserTool


def process_args(args):
    for grammar in args.grammar:
        if not exists(grammar):
            raise ValueError(f'{grammar} does not exist.')

    if not args.parser_dir:
        args.parser_dir = join(args.out, 'grammars')

    args.transformer = import_list(args.transformer)


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
    parser.add_argument('--max-depth', type=int, default=RuleSize.max.depth,
                        help='maximum expected tree depth (deeper tests will be discarded (default: %(default)f)).')
    parser.add_argument('-o', '--out', metavar='DIR', default=os.getcwd(),
                        help='directory to save the trees (default: %(default)s).')
    parser.add_argument('--parser-dir', metavar='DIR',
                        help='directory to save the parser grammars (default: <OUTDIR>/grammars).')
    add_tree_format_argument(parser)
    add_encoding_argument(parser, help='input file encoding (default: %(default)s).')
    add_encoding_errors_argument(parser)
    add_disable_cleanup_argument(parser)
    add_jobs_argument(parser)
    add_antlr_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    init_logging()
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)
    process_antlr_argument(args)
    process_tree_format_argument(args)
    try:
        process_args(args)
    except ValueError as e:
        parser.error(e)

    with ParserTool(grammars=args.grammar, hidden=args.hidden, transformers=args.transformer, parser_dir=args.parser_dir, antlr=args.antlr, rule=args.rule,
                    population=DefaultPopulation(args.out, args.tree_extension, codec=args.tree_codec), max_depth=args.max_depth, cleanup=args.cleanup, encoding=args.encoding, errors=args.encoding_errors) as parser:
        if args.jobs > 1:
            with Pool(args.jobs) as pool:
                for _ in pool.imap_unordered(parser.parse, args.input):
                    pass
        else:
            for fn in args.input:
                parser.parse(fn)


if __name__ == '__main__':
    execute()
