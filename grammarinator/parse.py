# Copyright (c) 2018-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import os
import shutil

from argparse import ArgumentParser
from math import inf
from multiprocessing import Pool
from os.path import basename, exists, join

from antlerinator import add_antlr_argument, process_antlr_argument
from antlr4 import CommonTokenStream, error, FileStream, ParserRuleContext, TerminalNode, Token
from inators.arg import add_log_level_argument, add_sys_path_argument, add_sys_recursion_limit_argument, add_version_argument, process_log_level_argument, process_sys_path_argument, process_sys_recursion_limit_argument
from inators.imp import import_object

from .cli import add_disable_cleanup_argument, add_jobs_argument, init_logging, logger
from .parser_builder import build_grammars
from .pkgdata import __version__
from .runtime import Tree, UnlexerRule, UnparserRule


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


class ParserFactory(object):
    """
    Class to parse existing sources and create Grammarinator-compatible tree representation
    from them. Uses ANTLR4 to create lexer and parser from a grammar. The created trees will
    keep the basename of the original source, but will be saved with ``.grt`` extension.
    These trees can be reused later by generation.
    """

    def __init__(self, grammars, parser_dir, antlr,
                 hidden=None, transformers=None, max_depth=inf, cleanup=True):
        """
        :param list[str] grammars: List of resources (grammars and additional sources) needed to parse the input.
        :param str parser_dir: Directory where grammars and the generated parser will be placed.
        :param str antlr: Path to the ANTLR4 tool (Java jar binary).
        :param list[str] hidden: List of hidden rule names that are expected to be added to the grammar tree (hidden rules are skipped by default).
        :param str or list[str] transformers: References to transformers to be applied to postprocess
               the parsed tree before serializing it. If it is a list, then each element should be a
               reference to a transformer. If it is a string, then it should be a JSON-formatted list of
               references. The references should be in package.module.function format.
        :param int max_depth: Maximum depth of trees. Deeper trees are not saved.
        :param bool cleanup: Boolean to enable the removal of the helper parser resources after processing the inputs.
        """
        self.max_depth = float(max_depth)
        self.cleanup = cleanup in [True, 1, 'True', 'true']
        transformers = transformers if isinstance(transformers, list) else json.loads(transformers) if transformers else []
        self.transformers = [import_object(transformer) if isinstance(transformer, str) else transformer for transformer in transformers]
        self.hidden = hidden if isinstance(hidden, list) else json.loads(hidden) if hidden else []

        self.parser_dir = parser_dir
        os.makedirs(self.parser_dir, exist_ok=True)

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

    def _antlr_to_grammarinator_tree(self, antlr_node, parser, visited=None):
        """
        Convert an ANTRL tree to Grammarinator tree.

        :param antlr4.ParserRuleContext or antlr4.TerminalNode antlr_node: Root of ANTLR tree to convert.
        :param antlr4.Parser parser: Parser object that created the ANTLR tree.
        :param set visited: Set of visited ANTLR nodes in the tree to be transformed.
        """
        if visited is None:
            visited = set()

        if isinstance(antlr_node, ParserRuleContext):
            rule_name = parser.ruleNames[antlr_node.getRuleIndex()]
            class_name = antlr_node.__class__.__name__

            # Check if the rule is a labeled alternative.
            if not class_name.lower().startswith(rule_name.lower()):
                alt_name = class_name[:-len('Context')] if class_name.endswith('Context') else class_name
                rule_name = f'{rule_name}_{alt_name[0].upper()}{alt_name[1:]}'

            node = UnparserRule(name=rule_name)
            assert node.name, 'Node name of a parser rule is empty or None.'
            for child in (antlr_node.children or []):
                node += self._antlr_to_grammarinator_tree(child, parser, visited)
        else:
            assert isinstance(antlr_node, TerminalNode), f'An ANTLR node must either be a ParserRuleContext or a TerminalNode but {antlr_node.__class__.__name__} was found.'
            name, text = (parser.symbolicNames[antlr_node.symbol.type], antlr_node.symbol.text) if antlr_node.symbol.type != Token.EOF else ('EOF', '')
            assert name, f'{name} is None or empty'

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

    # Create an ANTLR tree from the input stream and convert it to Grammarinator tree.
    def _create_tree(self, input_stream, rule, fn=None):
        try:
            parser = self.parser_cls(CommonTokenStream(self.lexer_cls(input_stream)))
            rule = rule or self.parser_cls.ruleNames[0]
            parse_tree_root = getattr(parser, rule)()
            if not parser._syntaxErrors:
                tree = Tree(self._antlr_to_grammarinator_tree(parse_tree_root, parser))

                for transformer in self.transformers:
                    tree.root = transformer(tree.root)

                return tree

            logger.warning('%s syntax errors detected%s.', parser._syntaxErrors, f' in {fn}' if fn else '')
        except Exception as e:
            logger.warning('Exception while parsing%s.', f' {fn}' if fn else '', exc_info=e)
        return None

    def tree_from_file(self, fn, rule, out, encoding):
        """
        Load content from file as ANTLR tree, convert it to Grammarinator tree and save it to file.

        :param str fn: Path to the input file.
        :param str rule: Name of the start rule.
        :param str out: Path to the output directory where the trees will be saved with `.grt`
               extension.
        :param str encoding: Encoding of the input file.
        """
        logger.info('Process file %s.', fn)
        try:
            tree = self._create_tree(FileStream(fn, encoding=encoding), rule, fn)
            if tree is not None:
                if not tree.save(join(out, basename(fn) + Tree.extension), max_depth=self.max_depth):
                    logger.info('The tree representation of %r is too deep. Skipping.', fn)
        except Exception as e:
            logger.warning('Exception while processing %s.', fn, exc_info=e)


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
    parser.add_argument('grammar', metavar='FILE', nargs='+',
                        help='ANTLR grammar files describing the expected format of input to parse.')
    parser.add_argument('-i', '--input', metavar='FILE', nargs='+', required=True,
                        help='input files to process.')
    parser.add_argument('-r', '--rule', metavar='NAME',
                        help='name of the rule to start parsing with (default: first parser rule).')
    parser.add_argument('-t', '--transformer', metavar='NAME', action='append', default=[],
                        help='reference to a transformer (in package.module.function format) to postprocess the parsed tree.')
    parser.add_argument('--hidden', metavar='NAME', action='append', default=[],
                        help='list of hidden tokens to be built into the parsed tree.')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='input file encoding (default: %(default)s).')
    parser.add_argument('--max-depth', type=int, default=inf,
                        help='maximum expected tree depth (deeper tests will be discarded (default: %(default)f)).')
    parser.add_argument('-o', '--out', metavar='DIR', default=os.getcwd(),
                        help='directory to save the trees (default: %(default)s).')
    parser.add_argument('--parser-dir', metavar='DIR',
                        help='directory to save the parser grammars (default: <OUTDIR>/grammars).')
    add_disable_cleanup_argument(parser)
    add_jobs_argument(parser)
    add_antlr_argument(parser)
    add_sys_path_argument(parser)
    add_sys_recursion_limit_argument(parser)
    add_log_level_argument(parser, short_alias=())
    add_version_argument(parser, version=__version__)
    args = parser.parse_args()

    for grammar in args.grammar:
        if not exists(grammar):
            parser.error(f'{grammar} does not exist.')

    if not args.parser_dir:
        args.parser_dir = join(args.out, 'grammars')

    init_logging()
    process_log_level_argument(args, logger)
    process_sys_path_argument(args)
    process_sys_recursion_limit_argument(args)
    process_antlr_argument(args)

    with ParserFactory(grammars=args.grammar, hidden=args.hidden, transformers=args.transformer, parser_dir=args.parser_dir, antlr=args.antlr,
                       max_depth=args.max_depth, cleanup=args.cleanup) as factory:
        if args.jobs > 1:
            with Pool(args.jobs) as pool:
                pool.starmap(factory.tree_from_file, iterate_tests(args.input, args.rule, args.out, args.encoding))
        else:
            for create_args in iterate_tests(args.input, args.rule, args.out, args.encoding):
                factory.tree_from_file(*create_args)


if __name__ == '__main__':
    execute()
