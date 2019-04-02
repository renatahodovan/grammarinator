# Copyright (c) 2017-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import argparse
import glob
import os
import re
import shlex
import subprocess
import sys

import antlerinator


tool_dir = os.path.dirname(os.path.abspath(__file__))


def collect_grammar_commands(grammars_dir):
    """
    Scan ANTLR v4 grammar files (*.g4) in a directory and find those, which
    contain test command comments (``// TEST-{command}: {commandline}``).

    :param grammars_dir: path to the directory to scan.
    :return: the found files and the found commands as an array of tuples in the
        structure of ``[(filename, [(command, commandline), ...]), ...]``.

    The result of the function can be used with pytest decorators as
    ``@pytest.mark.parametrize('grammar, commands', collect_grammar_commands('...'))``.
    """
    params = []
    for grammar in glob.iglob(os.path.join(grammars_dir, '*.g4')):
        with open(grammar, 'r') as f:
            commands = []
            for line in f:
                markup_match = re.match(r'^\s*//\s*TEST-([A-Z]+)\s*:(.*)$', line)
                if markup_match is not None:
                    command = markup_match.group(1)
                    commandline = markup_match.group(2).strip()
                    commands.append((command, commandline))
            if commands:
                params.append((grammar, commands))
    return params


def run_subprocess(grammar, commandline, tmpdir):
    """
    Helper function for test command runners to execute a subprocess.

    :param grammar: file name of the grammar that contained the test command.
    :param commandline: a template string for command line of the subprocess.
    :param tmpdir: path to a temporary directory (provided by the environment).

    Placeholders ``{grammar}`` and ``{tmpdir}`` can be used in ``commandline``,
    and will be replaced with the grammar name (NOT the grammar file name but
    the name of the grammar derived from it!) and the path to the temporary
    directory, respectively. The subprocess will be executed from the directory
    of the grammar file, and the execution environment will contain the
    ``PYTHONPATH`` variable with ``tmpdir`` appended.
    """
    grammar_name = os.path.basename(grammar)
    for suffix in ['.g4', 'Lexer', 'Parser']:
        if grammar_name.endswith(suffix):
            grammar_name = grammar_name[:-len(suffix)]

    grammar_dir = os.path.dirname(grammar)

    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.environ.get('PYTHONPATH', ''), tmpdir]))

    commandline = commandline.format(grammar=grammar_name, tmpdir=tmpdir)

    print('RUN: %s' % commandline)
    proc = subprocess.Popen(shlex.split(commandline, posix=sys.platform != 'win32'),
                            cwd=grammar_dir, env=env)
    proc.communicate()
    assert proc.returncode == 0


def run_process(grammar, commandline, tmpdir):
    """
    'PROCESS' test command runner. It will call ``grammarinator-process`` with
    the specified command line. Tests whether the processing of the grammar
    (creating a fuzzer from it) is working properly.

    :param grammar: file name of the grammar that contained the test command.
    :param commandline: command line as specified in the test command.
    :param tmpdir: path to a temporary directory (provided by the environment).
    """
    run_subprocess(grammar,
                   '{python} -m grammarinator.process {commandline}'
                   .format(python=sys.executable, commandline=commandline),
                   tmpdir)


def run_generate(grammar, commandline, tmpdir):
    """
    'GENERATE' test command runner. It will call ``grammarinator-generate`` with
    the specified command line. Tests whether a created fuzzer (a pair of
    unparser and unlexer) is generating output properly.

    :param grammar: file name of the grammar that contained the test command.
    :param commandline: command line as specified in the test command.
    :param tmpdir: path to a temporary directory (provided by the environment).
    """
    run_subprocess(grammar,
                   '{python} -m grammarinator.generate {commandline}'
                   .format(python=sys.executable, commandline=commandline),
                   tmpdir)


def run_antlr(grammar, commandline, tmpdir):
    """
    'ANTLR' test command runner. It will call the ANTLR v4 parser/lexer
    generator tool for Python 3 target with the specified command line. Tests
    whether a grammar is valid for ANTLR v4.

    :param grammar: file name of the grammar that contained the test command.
    :param commandline: command line as specified in the test command.
    :param tmpdir: path to a temporary directory (provided by the environment).
    """
    antlerinator.install(lazy=True)
    run_subprocess(grammar,
                   'java -jar {antlr} -Dlanguage=Python3 {commandline}'
                   .format(antlr=antlerinator.antlr_jar_path, commandline=commandline),
                   tmpdir)


def run_parse(grammar, commandline, tmpdir):
    """
    'PARSE' test command runner. It will call a simple parser/lexer harness with
    the specified command line. Tests whether outputs generated by a fuzzer are
    valid inputs according to the grammar the fuzzer is based on.

    :param grammar: file name of the grammar that contained the test command.
    :param commandline: command line as specified in the test command.
    :param tmpdir: path to a temporary directory (provided by the environment).
    """
    run_subprocess(grammar,
                   '{python} {parser} {commandline}'
                   .format(python=sys.executable, parser=os.path.join(tool_dir, 'parse.py'), commandline=commandline),
                   tmpdir)


command_runner = {
    "PROCESS": run_process,
    "GENERATE": run_generate,
    "ANTLR": run_antlr,
    "PARSE": run_parse,
}


def run_grammar(grammar, commands, tmpdir):
    """
    Run test commands for a grammar. Works well with the results of
    ``collect_grammar_commands``.

    :param grammar: file name of the grammar that contained the test commands.
    :param commands: an array of tuples of commands and command lines. Valid
        test commands are 'PROCESS', 'GENERATE', 'ANTLR', and 'PARSE'.
    :param tmpdir: path to a temporary directory (provided by the environment).
    """
    for command, commandline in commands:
        command_runner[command](grammar, commandline, tmpdir)


def execute():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description='Grammarinator: Grammar Test Command Runner')
    parser.add_argument('grammars_dir', metavar='DIR', default=os.getcwd(),
                        help='directory of grammars (default: %(default)s).')
    parser.add_argument('--tmpdir', metavar='DIR', default=os.getcwd(),
                        help='temporary directory (default: %(default)s).')
    args = parser.parse_args()

    os.makedirs(args.tmpdir, exist_ok=True)

    for grammar, commands in collect_grammar_commands(args.grammars_dir):
        run_grammar(grammar, commands, args.tmpdir)


if __name__ == '__main__':
    execute()
