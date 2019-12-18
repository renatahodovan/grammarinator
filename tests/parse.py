# Copyright (c) 2017-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import glob
import importlib
import logging
import sys

from argparse import ArgumentParser
from os import getcwd
from os.path import basename, dirname, join, splitext

from antlr4 import *

logger = logging.getLogger('grammarinator')


def parse(lexer_cls, parser_cls, rule, infile, encoding):
    logger.info('Parsing {infile}'.format(infile=infile))

    parser = parser_cls(CommonTokenStream(lexer_cls(FileStream(infile, encoding=encoding))))
    getattr(parser, rule)()

    if parser._syntaxErrors > 0:
        logger.error('Parse error in {infile}'.format(infile=infile))
    return parser._syntaxErrors


def import_entity(name):
    steps = name.split('.')
    module_name = '.'.join(steps[0:-1])
    entity_name = steps[-1]
    module = importlib.import_module(module_name)
    return eval('module.' + entity_name)


def execute():
    parser = ArgumentParser(description='Grammarinator: Test Parser')
    parser.add_argument('-p', '--parser', required=True, metavar='FILE',
                        help='antlr-generated parser.')
    parser.add_argument('-l', '--lexer', required=True, metavar='FILE',
                        help='antlr-generated lexer.')
    parser.add_argument('-r', '--rule', required=True, metavar='NAME',
                        help='name of the rule to start parsing from.')
    parser.add_argument('infile', metavar='FILE', default=join(getcwd(), 'test_%d'),
                        help='input file name pattern (default: %(default)s).')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='input file encoding (default: %(default)s).')
    parser.add_argument('--log-level', default='INFO', metavar='LEVEL',
                        help='verbosity level of diagnostic messages (default: %(default)s).')
    args = parser.parse_args()

    logging.basicConfig(format='%(message)s')
    logger.setLevel(args.log_level)

    if '%d' not in args.infile:
        base, ext = splitext(args.infile)
        args.infile = '{base}%d{ext}'.format(base=base, ext=ext) if ext else join(base, '%d')

    args.infile = args.infile.replace('%d', '*')

    sys.path.append(dirname(args.parser))
    lexer = splitext(basename(args.lexer))[0]
    parser = splitext(basename(args.parser))[0]

    lexer_cls = import_entity('.'.join([lexer, lexer]))
    parser_cls = import_entity('.'.join([parser, parser]))

    parsed = 0
    errors = 0
    for infile in glob.iglob(args.infile):
        parsed += 1
        errors += parse(lexer_cls, parser_cls, args.rule, infile, args.encoding)

    if not parsed:
        logger.error('No input file found for pattern {infile}'.format(infile=args.infile))
        errors += 1

    if errors > 0:
        sys.exit(1)


if __name__ == '__main__':
    execute()
