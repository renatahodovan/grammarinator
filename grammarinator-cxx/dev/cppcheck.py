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

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    subprocess.run(['cppcheck', '--language=c++', '--quiet',
                    '--enable=warning,style,performance,portability,information',
                    '--check-level=exhaustive',
                    '--suppressions-list=.cppcheck-suppress.txt',
                    '--template={file}:{line}: {severity}({id}): {message}',
                    '--error-exitcode=1',
                    '-Ilibgrammarinator/include',
                    '-Ilibgrlf/include']
                   + glob.glob('libgrammarinator/**/*.hpp', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('common/**/*.h', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('libgrlf/**/*.h', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('libgrlf/**/*.cpp', root_dir=PROJECT_DIR, recursive=True)
                   + glob.glob('tools/**/*.cpp', root_dir=PROJECT_DIR, recursive=True),
                   cwd=PROJECT_DIR)


if __name__ == '__main__':
    main()
