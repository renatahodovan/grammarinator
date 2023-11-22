# Copyright (c) 2020-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import os

from inators.imp import import_object

from .tool import JsonTreeCodec, PickleTreeCodec

logger = logging.getLogger('grammarinator')


def init_logging():
    logging.basicConfig(format='%(message)s')


def import_list(lst):
    return [import_object(item) for item in lst]


def add_jobs_argument(parser):
    parser.add_argument('-j', '--jobs', metavar='NUM', type=int, default=os.cpu_count(),
                        help='parallelization level (default: number of cpu cores (%(default)d)).')


def add_disable_cleanup_argument(parser):
    parser.add_argument('--disable-cleanup', dest='cleanup', default=True, action='store_false',
                        help='disable the removal of intermediate files.')


def add_encoding_argument(parser, help):
    parser.add_argument('--encoding', metavar='NAME', default='utf-8',
                        help=help)


def add_encoding_errors_argument(parser):
    parser.add_argument('--encoding-errors', metavar='NAME', default='strict',
                        help='encoding error handling scheme (default: %(default)s).')


tree_formats = {
    'pickle': {'extension': 'grtp', 'codec_class': PickleTreeCodec},
    'json': {'extension': 'grtj', 'codec_class': JsonTreeCodec},
}


def add_tree_format_argument(parser):
    parser.add_argument('--tree-format', metavar='NAME', choices=sorted(tree_formats.keys()), default='pickle',
                        help='format of the saved trees (choices: %(choices)s, default: %(default)s)')


def process_tree_format_argument(args):
    tree_format = tree_formats[args.tree_format]
    args.tree_extension = tree_format['extension']
    args.tree_codec = tree_format['codec_class']()
