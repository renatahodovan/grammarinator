#!/usr/bin/env python3

# Copyright (c) 2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import os
import shutil
import subprocess

from argparse import ArgumentParser, SUPPRESS

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def generate_build_options(args):
    build_options = []

    def build_options_append(cmakeopt, cliarg):
        if cliarg:
            build_options.append(f'-D{cmakeopt}={cliarg}')

    build_options_append('CMAKE_BUILD_TYPE', args.build_type)
    build_options_append('CMAKE_VERBOSE_MAKEFILE', 'ON' if args.verbose else 'OFF')
    build_options_append('CMAKE_INSTALL_PREFIX', args.install)
    build_options_append('GRAMMARINATOR_TOOLS', 'ON' if args.tools else 'OFF')
    build_options_append('GRAMMARINATOR_GRLF', 'ON' if args.grlf else 'OFF')
    build_options_append('GRAMMARINATOR_FUZZNULL', 'ON' if args.fuzznull else 'OFF')
    if args.tools or args.grlf or args.fuzznull:
        build_options_append('GRAMMARINATOR_GENERATOR', args.generator)
        build_options_append('GRAMMARINATOR_MODEL', args.model)
        build_options_append('GRAMMARINATOR_LISTENER', args.listener)
        build_options_append('GRAMMARINATOR_TRANSFORMER', args.transformer)
        build_options_append('GRAMMARINATOR_SERIALIZER', args.serializer)
        build_options_append('GRAMMARINATOR_TREECODEC', args.treecodec)
        build_options_append('GRAMMARINATOR_INCLUDE', args.include)
        build_options_append('GRAMMARINATOR_INCLUDEDIR', os.path.abspath(args.includedir))
        build_options_append('GRAMMARINATOR_SUFFIX', args.suffix)
    return build_options


def configure_output_dir(args):
    args.builddir = os.path.join(os.path.abspath(args.builddir), args.build_type)

    if args.clean and os.path.exists(args.builddir):
        shutil.rmtree(args.builddir)

    if not os.path.exists(args.builddir):
        os.makedirs(args.builddir)


def configure_cmake(args):
    configure_output_dir(args)
    #conan install conanfile.txt -s compiler=clang -s compiler.version=15 -s compiler.cppstd=20 --build=missing --remote conancenter --output-folder=build/

    subprocess.run(['conan', 'install', 'conanfile.txt', '-s', 'compiler=clang', '-s', 'compiler.version=15', '-s', 'compiler.cppstd=20', '--build=missing', '--remote', 'conancenter', f'--output-folder={args.builddir}', '-s', f'build_type={args.build_type}'], cwd=PROJECT_DIR)
    build_options = generate_build_options(args)
    subprocess.run(['cmake', '-S', PROJECT_DIR, '-B', args.builddir, *build_options], cwd=PROJECT_DIR)


def cmake_build(args):
    cmd = ['cmake', '--build', args.builddir]
    if args.verbose:
        cmd.append('--verbose')
    subprocess.run(cmd, cwd=PROJECT_DIR)


def cmake_install(args):
    if args.install is not None:
        cmd = ['cmake', '--install', args.builddir]
        subprocess.run(cmd, cwd=PROJECT_DIR)


def main():
    parser = ArgumentParser()

    ggrp = parser.add_argument_group('general build options')
    ggrp.add_argument('--builddir', metavar='DIR', default=os.path.join(PROJECT_DIR, 'build'),
                      help='directory for the build files (default: %(default)s)')
    ggrp.add_argument('--clean', default=False, action='store_true',
                      help='create a clean build (default: %(default)s)')
    ggrp.add_argument('--build-type', metavar='TYPE', choices=['Release', 'Debug'], default='Release',
                      help='set build type (default: %(default)s)')
    ggrp.add_argument('--debug', dest='build_type', action='store_const', const='Debug', default=SUPPRESS,
                      help='debug build (alias for --build-type %(const)s)')
    ggrp.add_argument('--verbose', default=False, action='store_true',
                      help='build target in verbose mode (default: %(default)s)')
    ggrp.add_argument('--install', metavar='DIR', nargs='?', default=None, const=False,
                      help='install after build (default: don\'t install; default directory if install: OS-specific)')

    sgrp = parser.add_argument_group('specialization options')
    sgrp.add_argument('--tools', default=False, action='store_true',
                      help='build a standalone blackbox generator tool for the given grammar (default: %(default)s)')
    sgrp.add_argument('--grlf', default=False, action='store_true',
                      help='build a static libgrlf library for libFuzzer integration (default: %(default)s)')
    sgrp.add_argument('--fuzznull', default=False, action='store_true',
                      help='build a dummy fuzznull binary to test libFuzzer integration without a real fuzz target (default: %(default)s)')
    sgrp.add_argument('--generator', metavar='NAME',
                      help='name of the generator class')
    sgrp.add_argument('--model', metavar='NAME',
                      help='name of the model class (default: grammarinator::runtime::DefaultModel)')
    sgrp.add_argument('--listener', metavar='NAME',
                      help='name of the listener class (default: grammarinator::runtime::Listener)')
    sgrp.add_argument('--transformer', metavar='NAME',
                      help='name of the transformer function')
    sgrp.add_argument('--serializer', metavar='NAME',
                      help='name of the serializer function (default: grammarinator::runtime::SimpleSpaceSerializer)')
    sgrp.add_argument('--tree-format', metavar='NAME', choices=['json', 'flatbuffers'],
                      help='format of the saved trees (choices: %(choices)s; default: flatbuffers)')
    sgrp.add_argument('--include', metavar='FILE',
                      help='file to include when compiling the specialized artefacts (default: derived from the generator class name by appending .hpp)')
    sgrp.add_argument('--includedir', metavar='DIR',
                      help='directory to append to the include path, usually which contains the file produced by grammarinator-process')
    sgrp.add_argument('--suffix', metavar='NAME',
                      help='suffix of the specialized artefacts, possibly referring to the input format (default: derived from the generator class name by removing Generator and lowercasing)')

    args = parser.parse_args()
    args.treecodec = {
        'flatbuffers':'FlatBuffersTreeCodec',
        'json': 'NlohmannJsonTreeCodec'
    }[args.tree_format] if args.tree_format else None

    if (args.grlf or args.tools) and (not args.includedir or not args.generator):
        parser.error('To build specialized artefacts, the `--generator` and `--includedir` arguments must be defined.')

    configure_cmake(args)
    cmake_build(args)
    cmake_install(args)


if __name__ == '__main__':
    main()
