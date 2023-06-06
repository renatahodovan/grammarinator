# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
# Copyright (c) 2020 Sebastian Kimberk.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import re

from argparse import ArgumentParser
from os import getcwd
from os.path import exists

from inators.arg import add_log_level_argument, add_version_argument, process_log_level_argument

from .cli import add_encoding_argument, add_encoding_errors_argument, init_logging, logger
from .pkgdata import __version__
from .tool import ProcessorTool


def execute():
    parser = ArgumentParser(description='Grammarinator: Processor', epilog="""
        The tool processes a grammar in ANTLR v4 format (*.g4, either separated
        to lexer and parser grammar files, or a single combined grammar) and
        creates a fuzzer that can generate randomized content conforming to
        the format described by the grammar.
        """)
    parser.add_argument('grammar', metavar='FILE', nargs='+',
                        help='ANTLR grammar files describing the expected format to generate.')
    parser.add_argument('-D', metavar='OPT=VAL', dest='options', default=[], action='append',
                        help='set/override grammar-level option')
    parser.add_argument('--language', metavar='LANG', choices=['py'], default='py',
                        help='language of the generated code (choices: %(choices)s; default: %(default)s)')
    parser.add_argument('--no-actions', dest='actions', default=True, action='store_false',
                        help='do not process inline actions.')
    parser.add_argument('--rule', '-r', metavar='NAME',
                        help='default rule to start generation from (default: the first parser rule)')
    parser.add_argument('--lib', metavar='DIR',
                        help='alternative location of import grammars.')
    parser.add_argument('--pep8', default=False, action='store_true',
                        help='enable autopep8 to format the generated fuzzer.')
    parser.add_argument('-o', '--out', metavar='DIR', default=getcwd(),
                        help='temporary working directory (default: %(default)s).')
    add_encoding_argument(parser, help='grammar file encoding (default: %(default)s).')
    add_encoding_errors_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    for grammar in args.grammar:
        if not exists(grammar):
            parser.error(f'{grammar} does not exist.')

    options = {}
    for option in args.options:
        parts = re.fullmatch('([^=]+)=(.*)', option)
        if not parts:
            parser.error(f'option not in OPT=VAL format: {option}')

        name, value = parts.group(1, 2)
        options[name] = value

    init_logging()
    process_log_level_argument(args, logger)

    ProcessorTool(args.language, args.out).process(args.grammar, options=options, default_rule=args.rule, encoding=args.encoding, errors=args.encoding_errors, lib_dir=args.lib, actions=args.actions, pep8=args.pep8)


if __name__ == '__main__':
    execute()
