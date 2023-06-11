#!/usr/bin/env python3

# Copyright (c) 2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import glob
import os
import subprocess

from argparse import ArgumentParser

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = ArgumentParser()
    parser.add_argument('--inplace', '-i', action='store_true')
    args = parser.parse_args()

    options = []
    if args.inplace:
        options += ['-i']
    else:
        options += ['--dry-run', '--Werror']

    subprocess.run(['clang-format'] + options
                   + glob.glob('libgrammarinator/**/*.hpp', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('common/**/*.h', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('libgrlf/**/*.h', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('libgrlf/**/*.cpp', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('tools/**/*.cpp', root_dir=PROJECT_DIR, recursive=True),
                   cwd=PROJECT_DIR)


if __name__ == '__main__':
    main()
