# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import antlerinator
import glob
import os
import pytest
import re
import shlex
import subprocess
import sys


tests_dir = os.path.dirname(os.path.abspath(__file__))
grammars_dir = os.path.join(tests_dir, 'grammars')


def collect_params():
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
    grammar_name = os.path.basename(grammar)
    for suffix in ['.g4', 'Lexer', 'Parser']:
        if grammar_name.endswith(suffix):
            grammar_name = grammar_name[:-len(suffix)]

    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.environ.get('PYTHONPATH', ''), tmpdir]))

    proc = subprocess.Popen(shlex.split(commandline.format(grammar=grammar_name, tmpdir=tmpdir), posix=sys.platform != 'win32'),
                            cwd=grammars_dir, env=env)
    proc.communicate()
    assert proc.returncode == 0


def run_process(grammar, commandline, tmpdir):
    run_subprocess(grammar,
                   '{python} -m grammarinator.process {commandline}'
                        .format(python=sys.executable, commandline=commandline),
                   tmpdir)


def run_generate(grammar, commandline, tmpdir):
    run_subprocess(grammar,
                   '{python} -m grammarinator.generate {commandline}'
                        .format(python=sys.executable, commandline=commandline),
                   tmpdir)


def run_antlr(grammar, commandline, tmpdir):
    antlerinator.install(lazy=True)
    run_subprocess(grammar,
                   'java -jar {antlr} -Dlanguage=Python3 {commandline}'
                        .format(antlr=antlerinator.antlr_jar_path, commandline=commandline),
                   tmpdir)


def run_parse(grammar, commandline, tmpdir):
    run_subprocess(grammar,
                   '{python} {parser} {commandline}'
                        .format(python=sys.executable, parser=os.path.join(tests_dir, 'parse.py'), commandline=commandline),
                   tmpdir)


command_runner = {
    "PROCESS": run_process,
    "GENERATE": run_generate,
    "ANTLR": run_antlr,
    "PARSE": run_parse,
}


@pytest.mark.parametrize('grammar, commands', collect_params())
def test_grammar(grammar, commands, tmpdir):
    for command, commandline in commands:
        command_runner[command](grammar, commandline, str(tmpdir))
