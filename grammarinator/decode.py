# Copyright (c) 2024-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import os

from argparse import ArgumentParser
from collections.abc import Callable
from functools import partial
from multiprocessing import Pool

from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument
from inators.imp import import_object

from .cli import add_encoding_argument, add_encoding_errors_argument, add_jobs_argument, add_tree_format_argument, init_logging, iter_files, logger, process_tree_format_argument
from .runtime import Rule
from .tool import TreeCodec
from .pkgdata import __version__


def decode(fn: str, codec: TreeCodec, serializer: Callable[[Rule], str], out: str, ext: str, encoding: str, errors: str) -> None:
    logger.info('Process file %s.', fn)
    with open(fn, 'rb') as f:
        root = codec.decode(f.read())

    if not root:
        logger.warning('File %s does not contain a valid tree.', fn)
        return

    base, _ = os.path.splitext(fn)
    out = os.path.join(out, f'{os.path.basename(base)}{ext}')

    with codecs.open(out, 'w', encoding=encoding, errors=errors) as f:
        f.write(serializer(root))


def execute() -> None:
    parser = ArgumentParser(description='Grammarinator: Decode',
                            epilog="""
                            The tool decodes tree files and serializes them to test cases.
                            """)
    parser.add_argument('-i', '--input', metavar='FILE', nargs='+',
                        help='input files to process')
    parser.add_argument('--glob', metavar='PATTERN', nargs='+',
                        help='wildcard pattern for input files to process (supported wildcards: ?, *, **, [])')
    parser.add_argument('--ext', default='.txt',
                        help='extension to use when saving decoded trees (default: %(default)s).')
    parser.add_argument('-s', '--serializer', metavar='NAME', default=str,
                        help='reference to a seralizer (in package.module.function format) that takes a tree and produces a string from it.')
    parser.add_argument('-o', '--out', metavar='DIR', default=os.getcwd(),
                        help='directory to save the test cases (default: %(default)s).')
    add_tree_format_argument(parser)
    add_encoding_argument(parser, help='output file encoding (default: %(default)s).')
    add_encoding_errors_argument(parser)
    add_jobs_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    init_logging()
    process_tree_format_argument(args)
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)

    os.makedirs(args.out, exist_ok=True)

    if isinstance(args.serializer, str):
        args.serializer = import_object(args.serializer)

    if args.jobs > 1:
        parallel_decode = partial(decode, codec=args.tree_codec, serializer=args.serializer, out=args.out, ext=args.ext, encoding=args.encoding, errors=args.encoding_errors)
        with Pool(args.jobs) as pool:
            for _ in pool.imap_unordered(parallel_decode, iter_files(args)):
                pass
    else:
        for fn in iter_files(args):
            decode(fn, args.tree_codec, args.serializer, args.out, args.ext, args.encoding, args.encoding_errors)


if __name__ == '__main__':
    execute()
