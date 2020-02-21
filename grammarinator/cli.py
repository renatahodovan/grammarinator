# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import os
import sys

import antlerinator

from .pkgdata import __version__, default_antlr_path

logger = logging.getLogger('grammarinator')


def add_version_argument(parser):
    parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))


def add_log_level_argument(parser):
    parser.add_argument('--log-level', metavar='LEVEL', default='INFO',
                        help='verbosity level of diagnostic messages (default: %(default)s).')


def process_log_level_argument(args):
    logging.basicConfig(format='%(message)s')
    logger.setLevel(args.log_level)


def add_sys_recursion_limit_argument(parser):
    parser.add_argument('--sys-recursion-limit', metavar='NUM', type=int, default=sys.getrecursionlimit(),
                        help='override maximum depth of the Python interpreter stack (default: %(default)d).')


def process_sys_recursion_limit_argument(args):
    sys.setrecursionlimit(args.sys_recursion_limit)


def add_antlr_argument(parser):
    parser.add_argument('--antlr', metavar='FILE', default=default_antlr_path,
                        help='path of the ANTLR jar file (default: %(default)s).')


def process_antlr_argument(args):
    if args.antlr == default_antlr_path:
        antlerinator.install(lazy=True)


def add_jobs_argument(parser):
    parser.add_argument('-j', '--jobs', metavar='NUM', type=int, default=os.cpu_count(),
                        help='parallelization level (default: number of cpu cores (%(default)d)).')


def add_disable_cleanup_argument(parser):
    parser.add_argument('--disable-cleanup', dest='cleanup', default=True, action='store_false',
                        help='disable the removal of intermediate files.')


def add_sys_path_argument(parser):
    parser.add_argument('--sys-path', metavar='DIR', action='append', default=[],
                        help='add directory to the search path for Python modules (may be specified multiple times)')


def process_sys_path_argument(args):
    for path in args.sys_path:
        if path not in sys.path:
            sys.path.append(path)
