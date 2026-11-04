# Copyright (c) 2024-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import os

import pytest

from antlerinator import default_antlr_jar_path
from antlr4 import CommonTokenStream, InputStream

from grammarinator.parse import ParserTool
from grammarinator.runtime import Annotations
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


# Compare conversion depth with the generator's annotation of the adjusted tree.
def test_parser_depth(tmpdir):
    tool = ParserTool(grammars=[os.path.join(parser_dir, 'Parse.g4')], rule='start', parser_dir=str(tmpdir), antlr=default_antlr_jar_path(), population=None)
    lexer = tool._lexer_cls(InputStream('pass?'))
    parser = tool._parser_cls(CommonTokenStream(lexer))
    root, depth, tokens, rules = tool._antlr_to_grammarinator_tree(parser.start(), parser)
    tool._adjust_tree_to_generator(rules)
    annotations = Annotations(root)
    assert depth == annotations.node_depths[root]
    assert tokens == annotations.node_tokens[root]
    assert depth == 4
    assert tokens == 2


# Reject parsed trees when their converted token count exceeds the limit, but
# keep those that reach it exactly.
@pytest.mark.parametrize('max_tokens, kept', [(1, False), (2, True)])
def test_parser_max_tokens(max_tokens, kept, tmpdir):
    tool = ParserTool(grammars=[os.path.join(parser_dir, 'Parse.g4')], rule='start', parser_dir=str(tmpdir), antlr=default_antlr_jar_path(),
                      population=None, max_tokens=max_tokens)
    assert (tool._create_tree(InputStream('pass?'), None) is not None) == kept
