# Copyright (c) 2024-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import os
import subprocess
import sys

from types import SimpleNamespace

import pytest

from antlerinator import default_antlr_jar_path
from antlr4 import CommonTokenStream, InputStream

from grammarinator.generate import process_args as process_generate_args
from grammarinator.parse import ParserTool
from grammarinator.runtime import Annotations
from grammarinator.tool import JsonTreeCodec
from grammarinator.tool import parser as parser_module
from grammarinator.tool.parser_stats import _bar, _distribution, _histogram, collect_tree_stats

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


# Check exact and power-of-two histograms and interpolated percentiles.
def test_parser_stats_distributions():
    values = list(range(1, 11))
    assert _distribution(values) == {'min': 1, 'p10': 1.9, 'median': 5.5, 'p90': 9.1, 'p95': 9.549999999999999, 'max': 10}
    assert _histogram([0, 1, 2, 3, 4, 8], powers=True) == {'0': 1, '1-1': 1, '2-3': 2, '4-7': 1, '8-15': 1}


# Ignore a unit rule even when an empty quantifier is also present.
def test_parser_nesting_depth(tmpdir):
    grammar = tmpdir.join('Unit.g4')
    grammar.write('grammar Unit;\nstart: inner (\',\' inner)? EOF;\ninner: WORD;\nWORD: [a-z]+;\n')
    tool = ParserTool(grammars=[str(grammar)], parser_dir=str(tmpdir.mkdir('unit-parser')), antlr=default_antlr_jar_path(), population=None)
    root = tool._create_tree(InputStream('x'), None)
    assert collect_tree_stats(root, None)['nesting_depth'] == 2


# Run corpus statistics with both worker counts and verify filtering and weights.
def test_parser_stats_jobs_and_limits(tmpdir):
    grammar = tmpdir.join('Stats.g4')
    grammar.write('grammar Stats;\nstart: chain EOF #Single | item item EOF #Pair;\nchain: item;\nitem: WORD;\nWORD: [a-z]+;\nWS: [ \\t\\r\\n]+ -> skip;\n')
    first, second = tmpdir.join('one.txt'), tmpdir.join('two.txt')
    first.write('foo')
    second.write('foo bar')
    reports = []
    for jobs in (1, 2):
        out = tmpdir.mkdir(f'out{jobs}')
        stats, weights = tmpdir.join(f'stats{jobs}.json'), tmpdir.join(f'weights{jobs}.json')
        subprocess.run([sys.executable, '-m', 'grammarinator.parse', str(first), str(second), '-g', str(grammar),
                        '-o', str(out), '--parser-dir', str(tmpdir.join(f'parser{jobs}')),
                        '--stats', str(stats), '--stats-weights', str(weights), '-j', str(jobs)], check=True)
        reports.append(json.loads(stats.read()))
        assert all(weight > 0 for rule in json.loads(weights.read())['alts'].values() for alt in rule.values() for weight in alt.values())
        args = SimpleNamespace(generator='grammarinator.runtime.Generator', model='grammarinator.runtime.DefaultModel', listener=[],
                               transformer=[], serializer=None, out='', weights=str(weights), population=None)
        process_generate_args(args)
        assert args.weights
    assert reports[0] == reports[1]
    assert reports[0]['counts']['kept'] == 2
    assert reports[0]['files'][0]['nesting_depth'] == 2
    assert reports[0]['files'][0]['depth'] == 5
    assert reports[0]['files'][0]['tokens'] == 1
    assert reports[0]['distributions']['depth']['median'] == 4.5
    assert reports[0]['histograms']['tokens'] == {'1-1': 1, '2-3': 1}
    limited = tmpdir.join('limited.json')
    subprocess.run([sys.executable, '-m', 'grammarinator.parse', str(first), str(second), '-g', str(grammar),
                    '-o', str(tmpdir.mkdir('limited-out')), '--parser-dir', str(tmpdir.join('limited-parser')),
                    '--max-depth', '4', '--max-tokens', '1', '--stats', str(limited), '-j', '1'], check=True)
    limited_report = json.loads(limited.read())
    assert limited_report['counts']['too_deep'] == 1
    assert limited_report['counts']['too_many_tokens'] == 1
    assert limited_report['filtered_by_limits'] == {'depth': 1, 'tokens': 1, 'both': 0}
    both = tmpdir.join('both.json')
    subprocess.run([sys.executable, '-m', 'grammarinator.parse', str(second), '-g', str(grammar),
                    '-o', str(tmpdir.mkdir('both-out')), '--parser-dir', str(tmpdir.join('both-parser')),
                    '--max-depth', '3', '--max-tokens', '1', '--stats', str(both), '-j', '1'], check=True)
    assert json.loads(both.read())['filtered_by_limits']['both'] == 1


# Run grammarinator-parse with statistics and return the report and the weights.
def _parse_with_stats(tmpdir, name, grammar, sources):
    grammar_file = tmpdir.join(f'{name}.g4')
    grammar_file.write(grammar)
    inputs = []
    for i, source in enumerate(sources):
        inputs.append(tmpdir.join(f'{name}{i}.txt'))
        inputs[-1].write(source)
    stats, weights = tmpdir.join(f'{name}-stats.json'), tmpdir.join(f'{name}-weights.json')
    subprocess.run([sys.executable, '-m', 'grammarinator.parse', *map(str, inputs), '-g', str(grammar_file),
                    '-o', str(tmpdir.mkdir(f'{name}-out')), '--parser-dir', str(tmpdir.join(f'{name}-parser')),
                    '--stats', str(stats), '--stats-weights', str(weights), '-j', '1'], check=True)
    return json.loads(stats.read()), json.loads(weights.read())


# Estimate quantifier probabilities from the decisions of the generator, and
# leave the unseen quantifiers to its default.
def test_parser_stats_weights(tmpdir):
    report, weights = _parse_with_stats(tmpdir, 'Quant', 'grammar Quant;\nstart: item (\',\' item)* EOF | \'x\' extra EOF;\n'
                                        'item: WORD (\'!\')?;\nextra: WORD (\';\' WORD)*;\nWORD: [a-z]+;\n',
                                        ['a!', 'b!,c'])
    assert report['counts']['kept'] == 2
    # (',' item)*: repetitions 0 and 1, i.e., 1 continue and 2 stops.
    assert weights['quants']['start']['0'] == pytest.approx(1 / 3)
    # '!'?: present twice and absent once, i.e., 2 continues and 1 stop (no stop decision at the maximum).
    assert weights['quants']['item']['0'] == pytest.approx(2 / 3)
    assert 'extra' not in weights['quants']
    assert weights['alts']['start']['0'] == {'0': pytest.approx(3 / 4), '1': pytest.approx(1 / 4)}


# Handle the alternations of negated token sets, which are not attached to a rule
# directly but to the quantifier that contains them.
def test_parser_stats_token_set(tmpdir):
    report, _ = _parse_with_stats(tmpdir, 'TokenSet', 'grammar TokenSet;\nstart: ~\'x\'* EOF;\nA: \'a\';\nB: \'b\';\nX: \'x\';\n',
                                  ['ab'])
    assert report['counts']['kept'] == 1
    assert '0' in report['alternatives']['by_rule']['start']


# Measure the self-embedding subtrees and the distinct subtrees of a rule.
def test_parser_stats_self_embedding(tmpdir):
    report, _ = _parse_with_stats(tmpdir, 'Nest', 'grammar Nest;\nstart: expr EOF;\nexpr: \'(\' expr \')\' | WORD;\nWORD: [a-z]+;\n',
                                  ['((a))'])
    assert report['self_embedding']['expr'] == {'different_subtrees': 2, 'shortest_ring': 1, 'fewest_wrap_tokens': 2}
    assert report['pool_diversity']['counts']['rule:expr'] == 3


# Scale the histogram bars to the largest bucket.
def test_parser_stats_bar():
    assert _bar(0, 1000) == ''
    assert _bar(1, 1000) == '#'
    assert _bar(500, 1000) == '#' * 20
    assert _bar(1000, 1000) == '#' * 40


# Keep the status of a tree when only the collection of its statistics fails.
def test_parser_stats_error(tmpdir, monkeypatch):
    # Simulate a bug in the statistics.
    def fail(root, codec):
        raise RuntimeError('statistics failed')

    monkeypatch.setattr(parser_module, 'collect_tree_stats', fail)
    source = tmpdir.join('source.txt')
    source.write('pass?')
    tool = ParserTool(grammars=[os.path.join(parser_dir, 'Parse.g4')], rule='start', parser_dir=str(tmpdir.mkdir('error-parser')),
                      antlr=default_antlr_jar_path(), population=None, stats=True)
    summary = tool.parse(str(source))
    assert summary['status'] == 'kept'
    assert summary['stats_error']
    assert summary['depth'] == 4
