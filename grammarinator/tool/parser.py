# Copyright (c) 2018-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging
import math
import os
import shutil
import sys

from os import listdir
from os.path import basename, commonprefix, split, splitext
from subprocess import CalledProcessError, PIPE, run

from antlr4 import CommonTokenStream, error, FileStream, ParserRuleContext, TerminalNode, Token

from ..runtime import RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantified, UnparserRuleQuantifier
from .processor import AlternationNode, AlternativeNode, LambdaNode, ProcessorTool, QuantifierNode, UnlexerRuleNode, UnparserRuleNode


logger = logging.getLogger(__name__)


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


class ExtendedErrorListener(error.ErrorListener.ErrorListener):
    """
    Custom error listener for the ANTLR lexer ensuring to insert the
    unrecognized tokens into the tree as well.
    """
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        recognizer.inputStream.consume()
        recognizer.type = Token.INVALID_TYPE
        recognizer.channel = Token.DEFAULT_CHANNEL
        recognizer.emit()
        recognizer.type = Token.MIN_USER_TOKEN_TYPE


class ParserTool:
    """
    Tool to parse existing sources and create a tree pool from them. These
    trees can be reused later by generation.
    """

    def __init__(self, grammars, parser_dir, antlr, population,
                 rule=None, hidden=None, transformers=None, max_depth=RuleSize.max.depth, strict=False,
                 lib_dir=None, cleanup=True, encoding='utf-8', errors='strict'):
        """
        :param list[str] grammars: List of resources (grammars and additional sources) needed to parse the input.
        :param str parser_dir: Directory where grammars and the generated parser will be placed.
        :param str antlr: Path to the ANTLR4 tool (Java jar binary).
        :param ~grammarinator.runtime.Population population: Tree pool where the
            trees will be saved, e.g., an instance of
            :class:`DefaultPopulation`.
        :param str rule: Name of the rule to start parsing with (default: first
            parser rule in the grammar).
        :param list[str] hidden: List of hidden rule names that are expected to be added to the grammar tree (hidden rules are skipped by default).
        :param list transformers: List of transformers to be applied to postprocess
               the parsed tree before serializing it.
        :param int or float max_depth: Maximum depth of trees. Deeper trees are not saved.
        :param bool strict: Tests that contain syntax errors are discarded.
        :param lib_dir: Alternative directory to look for grammar imports beside the current working directory.
        :param bool cleanup: Boolean to enable the removal of the helper parser resources after processing the inputs.
        :param str encoding: Encoding of the input file.
        :param str errors: Encoding error handling scheme.
        """
        self._population = population
        self._hidden = hidden or []
        self._transformers = transformers or []
        self._max_depth = max_depth
        self._strict = strict
        self._cleanup = cleanup
        self._encoding = encoding
        self._errors = errors

        self._parser_dir = parser_dir
        os.makedirs(self._parser_dir, exist_ok=True)

        lexer_root, parser_root = ProcessorTool.parse_grammars(grammars, parser_dir, encoding, errors, lib_dir)
        self._graph = ProcessorTool.build_graph(False, lexer_root, parser_root, None, rule)

        for i, grammar in enumerate(grammars):
            shutil.copy(grammar, self._parser_dir)
            grammars[i] = basename(grammar)

        self._lexer_cls, self._parser_cls, self._listener_cls = self._build_grammars(grammars, self._parser_dir, antlr, lib_dir)

        self._rule = rule or self._parser_cls.ruleNames[0]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._cleanup:
            shutil.rmtree(self._parser_dir, ignore_errors=True)

    @staticmethod
    def _build_grammars(in_files, out, antlr, lib_dir=None):
        """
        Build lexer and grammar from ANTLRv4 grammar files in Python3 target.

        :param in_files: List resources (grammars and additional sources) needed to parse the input.
        :param out: Directory where grammars are placed and where the output will be generated to.
        :param antlr: Path to the ANTLR4 tool (Java jar binary).
        :param lib_dir: Alternative directory to look for grammar imports beside the current working directory.
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
                run(('java', '-jar', antlr, languages['python']['antlr_arg']) + (('-lib', lib_dir) if lib_dir else ()) + grammars,
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
        rules = set()

        if visited is None:
            visited = set()

        if isinstance(antlr_node, ParserRuleContext):
            rule_name = parser.ruleNames[antlr_node.getRuleIndex()]
            class_name = antlr_node.__class__.__name__
            # Temporary use tuples as rule names to ease their comparison with grammar nodes,
            # while adjusting the decision nodes. However, they will be stringified eventually.
            node = UnparserRule(name=(rule_name,))
            rules.add(node)
            parent_node = node

            # Check if the rule is a labeled alternative.
            if class_name.endswith('Context') and class_name.lower() != rule_name.lower() + 'context':
                alt_name = class_name[:-len('Context')]
                labeled_alt_node = UnparserRule(name=(rule_name, alt_name[0].upper() + alt_name[1:]))
                rules.add(labeled_alt_node)
                node += labeled_alt_node
                parent_node = labeled_alt_node

            assert node.name, 'Node name of a parser rule is empty or None.'
            depth = 0
            for antlr_child in (antlr_node.children or []):
                child, child_depth, child_rules = self._antlr_to_grammarinator_tree(antlr_child, parser, visited)
                if not child:
                    continue
                rules.update(child_rules)
                parent_node += child
                depth = max(depth, child_depth + 1)
        else:
            assert isinstance(antlr_node, TerminalNode), f'An ANTLR node must either be a ParserRuleContext or a TerminalNode but {antlr_node.__class__.__name__} was found.'
            name, text = parser.symbolicNames[antlr_node.symbol.type] if len(parser.symbolicNames) > antlr_node.symbol.type else '<INVALID>', antlr_node.symbol.text
            assert name, f'{name} is None or empty'

            if antlr_node.symbol.type == Token.EOF:
                return None, 0, []

            if not self._hidden:
                node = UnlexerRule(name=(name,), src=text, immutable=(name,) in self._graph.immutables)
                rules.add(node)
            else:
                node = []
                hidden_tokens_to_left = parser.getTokenStream().getHiddenTokensToLeft(antlr_node.symbol.tokenIndex, -1) or []
                for token in hidden_tokens_to_left:
                    if parser.symbolicNames[token.type] in self._hidden:
                        if token not in visited:
                            hidden_name = (parser.symbolicNames[token.type],)
                            node.append(UnlexerRule(name=hidden_name, src=token.text, immutable=hidden_name in self._graph.immutables))
                            visited.add(token)

                node.append(UnlexerRule(name=(name,), src=text, immutable=(name,) in self._graph.immutables))
                hidden_tokens_to_right = parser.getTokenStream().getHiddenTokensToRight(antlr_node.symbol.tokenIndex, -1) or []
                for token in hidden_tokens_to_right:
                    if parser.symbolicNames[token.type] in self._hidden:
                        if token not in visited:
                            hidden_name = (parser.symbolicNames[token.type],)
                            node.append(UnlexerRule(name=hidden_name, src=token.text, immutable=hidden_name in self._graph.immutables))
                            visited.add(token)
                rules.update(node)
            depth = 0
        return node, depth, rules

    # The parse trees generated by the ANTLR parser consist solely of a rule hierarchy, lacking
    # information about the decisions made during parsing. As a result, they do not include
    # alternative, quantifier, or quantified nodes in the output tree, unlike the generator tool.
    # The function below reconstructs such structures. The concept is that since we can assign
    # to every tree node a grammar rule that produced it, it is sufficient to perform the
    # matching - and hence the reconstruction - on a single rule level. In other words, there is
    # no need to recursively match the entire tree.
    def _adjust_tree_to_generator(self, rules):

        def _adjust_rule(rule):
            def _match_seq(grammar_vertices, tree_node_pos):
                seq_children = []

                for vertex_pos, vertex in enumerate(grammar_vertices):
                    if vertex is None:  # end-of-rule marker
                        return seq_children if tree_node_pos == len(tree_nodes) else None, tree_node_pos

                    if isinstance(vertex, LambdaNode):
                        continue

                    if isinstance(vertex, UnparserRuleNode):
                        if tree_node_pos < len(tree_nodes) and isinstance(tree_nodes[tree_node_pos], UnparserRule) and vertex.name == '_'.join(tree_nodes[tree_node_pos].name):
                            seq_children += [tree_nodes[tree_node_pos]]
                            tree_node_pos += 1
                            continue
                        return None, tree_node_pos

                    if isinstance(vertex, UnlexerRuleNode):
                        if (tree_node_pos < len(tree_nodes) and isinstance(tree_nodes[tree_node_pos], UnlexerRule)
                            and (vertex.name == '_'.join(tree_nodes[tree_node_pos].name)
                                 or tree_nodes[tree_node_pos].name == ('<INVALID>',) and vertex.name.startswith('T__') and tree_nodes[tree_node_pos].src == vertex.out_neighbours[0].src)):
                            seq_children += [tree_nodes[tree_node_pos]]
                            tree_node_pos += 1
                            continue
                        return None, tree_node_pos

                    if isinstance(vertex, AlternationNode):
                        for alternative_vertex in vertex.out_neighbours:
                            assert isinstance(alternative_vertex, AlternativeNode), alternative_vertex
                            out_neighbours = alternative_vertex.out_neighbours
                            # If the next alternative is a labelled alternative with recurring name, then
                            # compare the tree nodes to the children of this alternative.
                            if (len(out_neighbours) == 1 and isinstance(out_neighbours[0], UnparserRuleNode)
                                    and len(out_neighbours[0].id) == 3 and out_neighbours[0].name == '_'.join(vertex.rule_id)):
                                out_neighbours = out_neighbours[0].out_neighbours
                            alt_children, alt_tree_node_pos = _match_seq(out_neighbours, tree_node_pos)
                            if alt_children is not None:
                                rest_children, rest_tree_node_pos = _match_seq(grammar_vertices[vertex_pos + 1:], alt_tree_node_pos)
                                if rest_children is not None:
                                    return seq_children + [(UnparserRuleAlternative(alt_idx=alternative_vertex.alt_idx, idx=alternative_vertex.idx), alt_children)] + rest_children, rest_tree_node_pos
                        return None, tree_node_pos

                    if isinstance(vertex, QuantifierNode):
                        quantifier_children = []

                        for _ in range(0, int(vertex.start)):
                            quant_children, quant_tree_node_pos = _match_seq(vertex.out_neighbours, tree_node_pos)
                            if quant_children is None:
                                return None, tree_node_pos
                            quantifier_children += [(UnparserRuleQuantified(), quant_children)]
                            tree_node_pos = quant_tree_node_pos

                        for _ in range(int(vertex.start), int(vertex.stop)) if vertex.stop != 'inf' else itertools.count():
                            quant_children, quant_tree_node_pos = _match_seq(vertex.out_neighbours, tree_node_pos)
                            if quant_children is None:
                                rest_children, rest_tree_node_pos = _match_seq(grammar_vertices[vertex_pos + 1:], tree_node_pos)
                                if rest_children is not None:
                                    return seq_children + [(UnparserRuleQuantifier(idx=vertex.idx, start=vertex.start, stop=vertex.stop if vertex.stop != 'inf' else math.inf), quantifier_children)] + rest_children, rest_tree_node_pos
                                return None, tree_node_pos
                            quantifier_children += [(UnparserRuleQuantified(), quant_children)]
                            tree_node_pos = quant_tree_node_pos

                        rest_children, rest_tree_node_pos = _match_seq(grammar_vertices[vertex_pos + 1:], tree_node_pos)
                        if rest_children is not None:
                            return seq_children + [(UnparserRuleQuantifier(idx=vertex.idx, start=vertex.start, stop=vertex.stop), quantifier_children)] + rest_children, rest_tree_node_pos

                        return None, tree_node_pos

                    assert False, vertex

                return seq_children, tree_node_pos

            # Separate regular and hidden children of a tree node
            tree_nodes, hidden_nodes = [], []
            prev_child = None
            for child in rule.children:
                if isinstance(child, UnlexerRule) and '_'.join(child.name) in self._hidden:
                    hidden_nodes.append((child, prev_child))
                else:
                    tree_nodes.append(child)
                prev_child = child

            # Match the right-hand side of the parser rule to the regular children of the tree node
            # They MUST match, since ANTLR has already parsed them
            # During matching, quantifier and alternation structures are identified
            rule_children, rule_tree_node_pos = _match_seq(self._graph.vertices[rule.name].out_neighbours + [None], 0)
            if rule_children is None:
                logger.warning('Failed to match %s tree node to the related grammar rule at %d.', rule.name, rule_tree_node_pos)
                return

            # Detach all children from the tree node so that they can be reattached
            # in a structured way afterwards
            for child in rule.children:
                child.parent = None
            rule.children = []

            # Reattach all regular children
            def _reattach_children(rule, children):
                for child in children:
                    if isinstance(child, tuple):
                        child, grandchildren = child
                        _reattach_children(child, grandchildren)
                    rule.add_child(child)

            _reattach_children(rule, rule_children)

            # Reattach all hidden children
            for child, prev_child in hidden_nodes:
                if prev_child is None:
                    rule.insert_child(0, child)
                else:
                    prev_child.parent.insert_child(prev_child.parent.children.index(prev_child) + 1, child)

        # Adjust all rules ...
        for rule in rules:
            # ... except for unlexer rules.
            if isinstance(rule, UnlexerRule) or not rule.children:
                continue
            _adjust_rule(rule)

        # Post-process parser rules to remove the artificial alternative inserted
        # above labelled alternatives with recurring label and fix the alternative
        # index of the root alternative of such constructs.
        for rule in rules:
            if not isinstance(rule, UnparserRule):
                continue

            for child in rule.children:
                if (isinstance(child, UnparserRuleAlternative)
                        and len(child.children) == 1 and isinstance(grandchild := child.children[0], UnparserRule)
                        and len(grandchild.children) == 1 and isinstance(grandgrandchild := grandchild.children[0], UnparserRuleAlternative)
                        and len(rule.name) == 1 and len(grandchild.name) == 2 and rule.name[0] == grandchild.name[0]
                        and child.alt_idx == grandgrandchild.alt_idx):
                    child.idx = grandgrandchild.idx
                    children_to_hoist = list(grandgrandchild.children)
                    grandgrandchild.remove()
                    grandchild.add_children(children_to_hoist)

        # Stringify rule names.
        for rule in rules:
            assert isinstance(rule.name, tuple), rule.name
            rule.name = '_'.join(rule.name)

    # Create an ANTLR tree from the input stream and convert it to Grammarinator tree.
    def _create_tree(self, input_stream, fn):
        try:
            lexer = self._lexer_cls(input_stream)
            lexer.addErrorListener(ExtendedErrorListener())
            parser = self._parser_cls(CommonTokenStream(lexer))
            parse_tree_root = getattr(parser, self._rule)()
            if parser._syntaxErrors:
                if self._strict:
                    logger.warning('%s syntax errors detected in %s. Skipping.', parser._syntaxErrors, fn)
                    return None
                logger.warning('%s syntax errors detected in %s.', parser._syntaxErrors, fn)

            root, depth, rules = self._antlr_to_grammarinator_tree(parse_tree_root, parser)
            if depth > self._max_depth:
                logger.warning('The tree representation of %s is %s, too deep. Skipping.', fn, depth)
                return None

            self._adjust_tree_to_generator(rules)
            for transformer in self._transformers:
                root = transformer(root)

            return root

        except Exception as e:
            logger.warning('Exception while parsing %s.', fn, exc_info=e)
        return None

    def parse(self, fn):
        """
        Load content from file, parse it to an ANTLR tree, convert it to
        Grammarinator tree, and save it to population.

        :param str fn: Path to the input file.
        """
        logger.info('Process file %s.', fn)
        try:
            root = self._create_tree(FileStream(fn, encoding=self._encoding, errors=self._errors), fn)
            if root is not None:
                self._population.add_individual(root, path=fn)
        except Exception as e:
            logger.warning('Exception while processing %s.', fn, exc_info=e)
