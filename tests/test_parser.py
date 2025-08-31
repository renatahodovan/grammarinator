# Copyright (c) 2024-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import os

import pytest

from antlerinator import default_antlr_jar_path
from antlr4 import InputStream

from grammarinator.parse import ParserTool
from grammarinator.tool import JsonTreeCodec

parser_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'parser')


@pytest.mark.parametrize('inp, expected', [
    (os.path.join(parser_dir, 'inp1.txt'), os.path.join(parser_dir, 'exp1.grtj')),
    (os.path.join(parser_dir, 'inp2.txt'), os.path.join(parser_dir, 'exp2.grtj')),
    (os.path.join(parser_dir, 'inp3.txt'), os.path.join(parser_dir, 'exp3.grtj')),
    (os.path.join(parser_dir, 'inp4.txt'), os.path.join(parser_dir, 'exp4.grtj')),
    (os.path.join(parser_dir, 'inp5.txt'), os.path.join(parser_dir, 'exp5.grtj')),
    (os.path.join(parser_dir, 'inp6.txt'), os.path.join(parser_dir, 'exp6.grtj')),
    (os.path.join(parser_dir, 'inp7.txt'), os.path.join(parser_dir, 'exp7.grtj')),
    (os.path.join(parser_dir, 'inp8.txt'), os.path.join(parser_dir, 'exp8.grtj')),
])
def test_parser(inp, expected, tmpdir):
    with open(inp, 'r') as f:
        src = f.read()

    tool = ParserTool(grammars=[os.path.join(parser_dir, 'Parse.g4')], rule='start', parser_dir=str(tmpdir), antlr=default_antlr_jar_path(), population=None)
    root = tool._create_tree(InputStream(src), None)
    assert root, f'Parsing of {inp} failed.'

    with open(expected, 'rb') as f:
        expected_root = JsonTreeCodec().decode(f.read())
    assert expected_root, f'Loading of {expected} failed.'

    assert root.equals(expected_root), f'{root:|} != {expected_root:|}'
