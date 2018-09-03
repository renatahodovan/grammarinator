# Copyright (c) 2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import importlib
import json
import logging
import shutil
import sys

import os
from os.path import basename, exists, join

from argparse import ArgumentParser
from multiprocessing import Pool

import antlerinator

from antlr4 import CommonTokenStream, error, FileStream, ParserRuleContext, TerminalNode, Token
from .parser_builder import build_grammars
from .pkgdata import __version__, default_antlr_path
from .runtime.tree import UnlexerRule, UnparserRule, Tree

logger = logging.getLogger('grammarinator')
logging.basicConfig(format='%(message)s')


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


def import_entity(name):
    steps = name.split('.')
    return getattr(importlib.import_module('.'.join(steps[0:-1])), steps[-1])


class ParserFactory(object):
    """
    Class to parse existing sources and create Grammarinator compatible tree representation
    from them. These trees can be reused later by generation.
    """

    def __init__(self, grammars, parser_dir,
                 hidden=None, transformers=None, antlr=default_antlr_path, max_depth='inf', cleanup=True):
        self.max_depth = max_depth if not isinstance(max_depth, str) else (float('inf') if max_depth == 'inf' else int(max_depth))
        self.cleanup = cleanup in [True, 1, 'True', 'true']
        transformers = transformers if isinstance(transformers, list) else json.loads(transformers) if transformers else []
        self.transformers = [import_entity(transformer) if isinstance(transformer, str) else transformer for transformer in transformers]
        self.hidden = hidden if isinstance(hidden, list) else json.loads(hidden) if hidden else []

        self.parser_dir = parser_dir
        os.makedirs(self.parser_dir, exist_ok=True)

        if self.parser_dir not in sys.path:
            sys.path.append(self.parser_dir)

        grammars = grammars if isinstance(grammars, list) else json.loads(grammars)
        for i, grammar in enumerate(grammars):
            shutil.copy(grammar, self.parser_dir)
            grammars[i] = basename(grammar)

        self.lexer_cls, self.parser_cls, self.listener_cls = build_grammars(grammars, self.parser_dir, antlr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cleanup:
            shutil.rmtree(self.parser_dir, ignore_errors=True)

    def antlr_to_grammarinator_tree(self, antlr_node, parser, visited=None):
        if visited is None:
            visited = set()

        if isinstance(antlr_node, ParserRuleContext):
            rule_name = parser.ruleNames[antlr_node.getRuleIndex()]
            class_name = antlr_node.__class__.__name__

            # Check if the rule is a labeled alternative.
            if not class_name.lower().startswith(rule_name.lower()):
                alt_name = class_name[:-len('Context')] if class_name.endswith('Context') else class_name
                rule_name = '{rule_name}_{alternative}'.format(
                    rule_name=rule_name,
                    alternative=alt_name[0].upper() + alt_name[1:])

            node = UnparserRule(name=rule_name)
            assert node.name, 'Node name of a parser rule is empty or None.'
            for child in (antlr_node.children or []):
                node += self.antlr_to_grammarinator_tree(child, parser, visited)
        else:
            assert isinstance(antlr_node, TerminalNode), 'An ANTLR node must either be a ParserRuleContext or a TerminalNode but {node_cls} was found.'.format(node_cls=antlr_node.__class__.__name__)
            name, text = (parser.symbolicNames[antlr_node.symbol.type], antlr_node.symbol.text) if antlr_node.symbol.type != Token.EOF else ('EOF', '')
            assert name, '{name} is None or empty'.format(name=name)

            if not self.hidden:
                node = UnlexerRule(name=name, src=text)
            else:
                hidden_tokens_to_left = parser.getTokenStream().getHiddenTokensToLeft(antlr_node.symbol.tokenIndex, -1) or []
                node = []
                for token in hidden_tokens_to_left:
                    if parser.symbolicNames[token.type] in self.hidden:
                        if token not in visited:
                            node.append(UnlexerRule(name=parser.symbolicNames[token.type], src=token.text))
                            visited.add(token)

                node.append(UnlexerRule(name=name, src=text))
                hidden_tokens_to_right = parser.getTokenStream().getHiddenTokensToRight(antlr_node.symbol.tokenIndex, -1) or []
                for token in hidden_tokens_to_right:
                    if parser.symbolicNames[token.type] in self.hidden:
                        if token not in visited:
                            node.append(UnlexerRule(name=parser.symbolicNames[token.type], src=token.text))
                            visited.add(token)
        return node

    def create_tree(self, input_stream, rule, fn=None):
        try:
            parser = self.parser_cls(CommonTokenStream(self.lexer_cls(input_stream)))
            rule = rule or self.parser_cls.ruleNames[0]
            parse_tree_root = getattr(parser, rule)()
            if not parser._syntaxErrors:
                tree = Tree(self.antlr_to_grammarinator_tree(parse_tree_root, parser))

                for transformer in self.transformers:
                    tree.root = transformer(tree.root)

                return tree

            logger.warning('%s syntax errors detected.', parser._syntaxErrors)
        except Exception as e:
            logger.warning('Exception in parsing.%s', ' [{fn}]'.format(fn=fn) if fn else '')
            logger.warning(e)
        return None

    def tree_from_file(self, fn, rule, out, encoding):
        logger.info('Process file %s.', fn)
        try:
            tree = self.create_tree(FileStream(fn, encoding=encoding), rule, fn)
            if tree is not None:
                tree.save(join(out, basename(fn) + Tree.extension), max_depth=self.max_depth)
        except Exception as e:
            logger.warning('Exception while processing %s: %s', fn, str(e))


def iterate_tests(files, rule, out, encoding):
    for test in files:
        yield (test, rule, out, encoding)


def execute():
    parser = ArgumentParser(description='Grammarinator: Parser',
                            epilog="""
                            The tool parses files with ANTLR v4 grammars, builds Grammarinator-
                            compatible tree representations from them and saves them for further
                            reuse.
                            """)
    parser.add_argument('files', nargs='+',
                        help='input files to process.')
    parser.add_argument('-g', '--grammars', nargs='+', metavar='FILE', required=True,
                        help='ANTLR grammar files describing the expected format of input to parse.')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start parsing with (default: first parser rule)')
    parser.add_argument('-t', '--transformers', metavar='LIST', nargs='+', default=[],
                        help='list of transformers (in package.module.function format) to postprocess the parsed tree.')
    parser.add_argument('--hidden', nargs='+', metavar='NAME',
                        help='list of hidden tokens to be built into the parsed tree.')
    parser.add_argument('--antlr', metavar='FILE', default=default_antlr_path,
                        help='path of the ANTLR jar file (default: %(default)s).')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='input file encoding (default: %(default)s).')
    parser.add_argument('--disable-cleanup', dest='cleanup', default=True, action='store_false',
                        help='disable the removal of intermediate files.')
    parser.add_argument('-j', '--jobs', default=os.cpu_count(), type=int, metavar='NUM',
                        help='parsing parallelization level (default: number of cpu cores (%(default)d)).')
    parser.add_argument('--max-depth', type=int, default=float('inf'),
                        help='maximum expected tree depth (deeper tests will be discarded (default: %(default)f)).')
    parser.add_argument('-o', '--out', metavar='DIR', default=os.getcwd(),
                        help='directory to save the trees (default: %(default)s).')
    parser.add_argument('--parser-dir', metavar='DIR',
                        help='directory to save the parser grammars (default: <OUTDIR>/grammars).')
    parser.add_argument('--sys-recursion-limit', metavar='NUM', type=int, default=sys.getrecursionlimit(),
                        help='override maximum depth of the Python interpreter stack (default: %(default)d)')
    parser.add_argument('--log-level', default='INFO', metavar='LEVEL',
                        help='verbosity level of diagnostic messages (default: %(default)s).')
    parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))
    args = parser.parse_args()

    for grammar in args.grammars:
        if not exists(grammar):
            parser.error('{grammar} does not exist.'.format(grammar=grammar))

    if not args.parser_dir:
        args.parser_dir = join(args.out, 'grammars')

    logger.setLevel(args.log_level)
    sys.setrecursionlimit(int(args.sys_recursion_limit))

    if args.antlr == default_antlr_path:
        antlerinator.install(lazy=True)

    with ParserFactory(grammars=args.grammars, hidden=args.hidden, transformers=args.transformers, parser_dir=args.parser_dir, antlr=args.antlr,
                       max_depth=args.max_depth, cleanup=args.cleanup) as factory:
        if args.jobs > 1:
            with Pool(args.jobs) as pool:
                pool.starmap(factory.tree_from_file, iterate_tests(args.files, args.rule, args.out, args.encoding))
        else:
            for create_args in iterate_tests(args.files, args.rule, args.out, args.encoding):
                factory.tree_from_file(*create_args)


if __name__ == '__main__':
    execute()
