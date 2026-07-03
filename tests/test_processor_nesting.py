# Copyright (c) 2017-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import ast
import importlib
import os
import subprocess
import sys

import pytest

grammars_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grammars')

# CPython caps statically-nested blocks per code object at CO_MAXBLOCKS.
MAX_BLOCKS = 20


def max_block_depth(node):
    """
    Ground-truth oracle for the number of statically-nested blocks CPython
    counts in a code object (``with``/``while``/``for``/``try``; ``if``/``elif``
    add nothing). Copied from Datadog/dd-parsers' ``flatten_deep_nesting.py``.
    Independent of grammarinator's internal block-cost table, so it guards
    against block-cost/template drift.
    """
    block_types = (ast.With, ast.AsyncWith, ast.While, ast.For, ast.AsyncFor, ast.Try)
    is_block = isinstance(node, block_types)

    child_max = 0
    for child in ast.iter_child_nodes(node):
        # Do not descend into nested function/class definitions: they own a
        # separate code object with its own block budget.
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        child_max = max(child_max, max_block_depth(child))

    return child_max + (1 if is_block else 0)


def process_grammar(grammar_name, tmpdir, language='py'):
    """Run grammarinator-process on a fixture grammar into ``tmpdir``."""
    grammar = os.path.join(grammars_dir, grammar_name + '.g4')
    subprocess.run([sys.executable, '-m', 'grammarinator.process', grammar,
                    '-o', str(tmpdir), '--language', language],
                   check=True)
    return os.path.join(str(tmpdir), grammar_name + 'Generator.' + language)


def import_generator(module_name, tmpdir):
    """Import a freshly generated generator module from ``tmpdir``."""
    sys.path.insert(0, str(tmpdir))
    try:
        if module_name in sys.modules:
            del sys.modules[module_name]
        return importlib.import_module(module_name)
    finally:
        sys.path.pop(0)


# deeply nested rule produces an importable Python module.
def test_deep_nesting_module_imports(tmpdir):
    process_grammar('DeepNesting', tmpdir)
    module = import_generator('DeepNestingGenerator', tmpdir)
    assert hasattr(module, 'DeepNestingGenerator')


# no generated method exceeds the static block limit.
def test_deep_nesting_no_method_exceeds_limit(tmpdir):
    src_path = process_grammar('DeepNesting', tmpdir)
    with open(src_path) as f:
        tree = ast.parse(f.read())
    over = [(node.name, max_block_depth(node))
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and max_block_depth(node) > MAX_BLOCKS]
    assert not over, f'methods exceeding {MAX_BLOCKS} blocks: {over}'


# the split generator still generates output.
def test_deep_nesting_generation_runs(tmpdir):
    process_grammar('DeepNesting', tmpdir)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.environ.get('PYTHONPATH', ''), str(tmpdir)]))
    subprocess.run([sys.executable, '-m', 'grammarinator.generate',
                    'DeepNestingGenerator.DeepNestingGenerator', '-r', 'start', '-n', '5',
                    '-o', os.path.join(str(tmpdir), 'out%d.txt')],
                   check=True, env=env)


# rules with a local_ctx (label/arg/local/return) survive extraction.
def test_deep_nesting_local_ctx_generation_runs(tmpdir):
    # `deepquant` has a labelled element deep inside the nesting: a fragment
    # extracted from it references local_ctx and would NameError without the param.
    process_grammar('DeepNesting', tmpdir)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.environ.get('PYTHONPATH', ''), str(tmpdir)]))
    subprocess.run([sys.executable, '-m', 'grammarinator.generate',
                    'DeepNestingGenerator.DeepNestingGenerator', '-r', 'deepquant', '-n', '5',
                    '-o', os.path.join(str(tmpdir), 'dq%d.txt')],
                   check=True, env=env)


# internal leading-underscore rules (`_dot`) coexist with split fragments.
def test_deep_nesting_leading_underscore_rule_imports(tmpdir):
    src_path = process_grammar('DeepNesting', tmpdir)
    with open(src_path) as f:
        src = f.read()
    # No fragment helper may collide with CPython name mangling (`__x` -> `_Class__x`).
    tree = ast.parse(src)
    frag_names = [node.name for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and '_frag_' in node.name]
    assert frag_names, 'expected fragment helpers in a deeply nested grammar'
    assert all(not name.startswith('__') for name in frag_names), frag_names
    import_generator('DeepNestingGenerator', tmpdir)


# a rule too deep for a single cut is split repeatedly into several fragments.
def test_deep_nesting_requires_multiple_splits(tmpdir):
    # `deeptwice` nests ~49 blocks: one cut leaves a piece still over the limit,
    # so the split must recurse and emit more than one fragment for the rule.
    src_path = process_grammar('DeepNesting', tmpdir)
    with open(src_path) as f:
        tree = ast.parse(f.read())
    deeptwice_frags = [node.name for node in ast.walk(tree)
                       if isinstance(node, ast.FunctionDef) and node.name.startswith('_deeptwice_frag_')]
    assert len(deeptwice_frags) >= 2, deeptwice_frags
    over = [(node.name, max_block_depth(node))
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and max_block_depth(node) > MAX_BLOCKS]
    assert not over, f'methods exceeding {MAX_BLOCKS} blocks: {over}'
    import_generator('DeepNestingGenerator', tmpdir)


# shallow grammars are untouched (no fragments), C++ is never split.
def test_shallow_grammar_has_no_fragments(tmpdir):
    src_path = process_grammar('Quantifiers', tmpdir)
    with open(src_path) as f:
        src = f.read()
    assert '_frag_' not in src


def test_cxx_target_has_no_fragments(tmpdir):
    src_path = process_grammar('DeepNesting', tmpdir, language='hpp')
    with open(src_path) as f:
        src = f.read()
    assert '_frag_' not in src
