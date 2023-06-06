# Copyright (c) 2018-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import logging
import os
import shutil
import sys

from math import inf
from os import listdir
from os.path import basename, commonprefix, join, split, splitext
from subprocess import CalledProcessError, PIPE, run

from antlr4 import CommonTokenStream, error, FileStream, ParserRuleContext, TerminalNode, Token
from inators.imp import import_object

from ..runtime import Tree, UnlexerRule, UnparserRule

logger = logging.getLogger(__name__)


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


class ParserTool(object):
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
        self._max_depth = float(max_depth)
        self._cleanup = cleanup in [True, 1, 'True', 'true']
        transformers = transformers if isinstance(transformers, list) else json.loads(transformers) if transformers else []
        self._transformers = [import_object(transformer) if isinstance(transformer, str) else transformer for transformer in transformers]
        self._hidden = hidden if isinstance(hidden, list) else json.loads(hidden) if hidden else []

        self._parser_dir = parser_dir
        os.makedirs(self._parser_dir, exist_ok=True)

        grammars = grammars if isinstance(grammars, list) else json.loads(grammars)
        for i, grammar in enumerate(grammars):
            shutil.copy(grammar, self._parser_dir)
            grammars[i] = basename(grammar)

        self._lexer_cls, self._parser_cls, self._listener_cls = self._build_grammars(grammars, self._parser_dir, antlr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cleanup:
            shutil.rmtree(self._parser_dir, ignore_errors=True)

    @staticmethod
    def _build_grammars(in_files, out, antlr):
        """
        Build lexer and grammar from ANTLRv4 grammar files in Python3 target.

        :param in_files: List resources (grammars and additional sources) needed to parse the input.
        :param out: Directory where grammars are placed and where the output will be generated to.
        :param antlr: Path to the ANTLR4 tool (Java jar binary).
        :return: List of references/names of the lexer, parser and listener classes of the target.
        """
        try:
            # TODO: support Java parsers too.
            languages = {
                'python': {'antlr_arg': '-Dlanguage=Python3',
                           'ext': 'py',
                           'listener_format': 'Listener'}
            }

            grammars = tuple(fn for fn in in_files if fn.endswith('.g4'))

            # Generate parser and lexer in the target language and return either with
            # python class ref or the name of java classes.
            try:
                run(('java', '-jar', antlr, languages['python']['antlr_arg']) + grammars,
                    stdout=PIPE, stderr=PIPE, cwd=out, check=True)
            except CalledProcessError as e:
                logger.error('Building grammars %r failed!\n%s\n%s\n', grammars,
                             e.stdout.decode('utf-8', 'ignore'),
                             e.stderr.decode('utf-8', 'ignore'))
                raise

            files = set(listdir(out)) - set(in_files)
            filename = basename(grammars[0])

            def file_endswith(end_pattern):
                return splitext(split(list(
                    filter(lambda x: len(commonprefix([filename, x])) > 0 and x.endswith(end_pattern), files))[0])[1])[0]

            # Extract the name of lexer and parser from their path.
            lexer = file_endswith(f'Lexer.{languages["python"]["ext"]}')
            parser = file_endswith(f'Parser.{languages["python"]["ext"]}')
            # The name of the generated listeners differs if Python or other language target is used.
            listener = file_endswith(f'{languages["python"]["listener_format"]}.{languages["python"]["ext"]}')

            # Add the path of the built lexer and parser to the Python path to be available for importing.
            if out not in sys.path:
                sys.path.append(out)

            return (getattr(__import__(x, globals(), locals(), [x], 0), x) for x in [lexer, parser, listener])
        except Exception as e:
            logger.error('Exception while loading parser modules', exc_info=e)
            raise

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

            if not self._hidden:
                node = UnlexerRule(name=name, src=text)
            else:
                hidden_tokens_to_left = parser.getTokenStream().getHiddenTokensToLeft(antlr_node.symbol.tokenIndex, -1) or []
                node = []
                for token in hidden_tokens_to_left:
                    if parser.symbolicNames[token.type] in self._hidden:
                        if token not in visited:
                            node.append(UnlexerRule(name=parser.symbolicNames[token.type], src=token.text))
                            visited.add(token)

                node.append(UnlexerRule(name=name, src=text))
                hidden_tokens_to_right = parser.getTokenStream().getHiddenTokensToRight(antlr_node.symbol.tokenIndex, -1) or []
                for token in hidden_tokens_to_right:
                    if parser.symbolicNames[token.type] in self._hidden:
                        if token not in visited:
                            node.append(UnlexerRule(name=parser.symbolicNames[token.type], src=token.text))
                            visited.add(token)
        return node

    # Create an ANTLR tree from the input stream and convert it to Grammarinator tree.
    def _create_tree(self, input_stream, rule, fn=None):
        try:
            parser = self._parser_cls(CommonTokenStream(self._lexer_cls(input_stream)))
            rule = rule or self._parser_cls.ruleNames[0]
            parse_tree_root = getattr(parser, rule)()
            if not parser._syntaxErrors:
                tree = Tree(self._antlr_to_grammarinator_tree(parse_tree_root, parser))

                for transformer in self._transformers:
                    tree.root = transformer(tree.root)

                return tree

            logger.warning('%s syntax errors detected%s.', parser._syntaxErrors, f' in {fn}' if fn else '')
        except Exception as e:
            logger.warning('Exception while parsing%s.', f' {fn}' if fn else '', exc_info=e)
        return None

    def parse(self, fn, rule, out, encoding, errors):
        """
        Load content from file, parse it to an ANTLR tree, convert it to Grammarinator tree, and save it to file.

        :param str fn: Path to the input file.
        :param str rule: Name of the start rule.
        :param str out: Path to the output directory where the trees will be saved with ``.grt``
               extension.
        :param str encoding: Encoding of the input file.
        :param str errors: Encoding error handling scheme.
        """
        logger.info('Process file %s.', fn)
        try:
            tree = self._create_tree(FileStream(fn, encoding=encoding, errors=errors), rule, fn)
            if tree is not None:
                if not tree.save(join(out, basename(fn) + Tree.extension), max_depth=self._max_depth):
                    logger.info('The tree representation of %r is too deep. Skipping.', fn)
        except Exception as e:
            logger.warning('Exception while processing %s.', fn, exc_info=e)
