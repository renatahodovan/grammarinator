# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import re

from argparse import ArgumentParser
from collections import defaultdict
from math import inf
from os import getcwd, makedirs
from os.path import dirname, exists, join
from pkgutil import get_data
from shutil import rmtree

import autopep8

from antlr4 import CommonTokenStream, FileStream, ParserRuleContext
from jinja2 import Environment

from .cli import add_antlr_argument, add_disable_cleanup_argument, add_log_level_argument, add_version_argument, process_antlr_argument, process_log_level_argument
from .parser_builder import build_grammars
from .pkgdata import __version__, default_antlr_path


class Node(object):

    def __init__(self, id):
        self.id = id
        self.out_neighbours = []
        self.min_depth = inf


class RuleNode(Node):

    def __init__(self, id, type):
        super().__init__(id)
        self.type = type
        self.has_var = False


class UnlexerRuleNode(RuleNode):

    def __init__(self, id):
        super().__init__(id, 'UnlexerRule')


class UnparserRuleNode(RuleNode):

    def __init__(self, id):
        super().__init__(id, 'UnparserRule')


class ImagRuleNode(Node):
    pass


class LiteralNode(Node):

    def __init__(self, id, src=None, charset=None, range=None, any=False):
        super().__init__(id)
        self.src = src
        self.charset = charset
        self.range = range
        self.any_char = any


class LambdaNode(Node):
    pass


class AlternationNode(Node):

    def __init__(self, id, idx, conditions):
        super().__init__(id)
        self.idx = idx
        self.conditions = conditions


class AlternativeNode(Node):
    pass


class QuantifierNode(Node):

    def __init__(self, id, idx, min, max):
        super().__init__(id)
        self.idx = idx
        self.min = min
        self.max = max


class ActionNode(Node):

    def __init__(self, id, src):
        super().__init__(id)
        self.src = src


class VariableNode(Node):

    def __init__(self, id, name):
        super().__init__(id)
        self.name = name


class Charset(object):

    def __init__(self, name, ranges, invert=False):
        self.name = name
        self.ranges = ranges
        self.invert = invert


class GrammarGraph(object):

    def __init__(self):
        self.name = None
        self.vertices = dict(lambda_0=LambdaNode(id='lambda_0'))
        self.options = dict()
        self.charsets = []
        self.header = ''
        self.member = ''
        self.default_rule = None

    @property
    def superclass(self):
        return self.options.get('superClass', 'Generator')

    @property
    def rules(self):
        return (vertex for vertex in self.vertices.values() if isinstance(vertex, RuleNode) and vertex.id != 'EOF')

    @property
    def imag_rules(self):
        return (vertex for vertex in self.vertices.values() if isinstance(vertex, ImagRuleNode))

    def add_node(self, node):
        self.vertices[node.id] = node

    def add_edge(self, frm, to):
        assert frm in self.vertices, '{frm} not in vertices.'.format(frm=frm)
        assert to in self.vertices, '{to} not in vertices.'.format(to=to)
        self.vertices[frm].out_neighbours.append(self.vertices[to])

    def calc_min_depths(self):
        min_depths = defaultdict(lambda: inf)
        changed = True

        while changed:
            changed = False
            for ident in self.vertices:
                selector = min if isinstance(self.vertices[ident], AlternationNode) else max
                min_depth = selector([min_depths[node.id] + int(isinstance(self.vertices[node.id], RuleNode))
                                      for node in self.vertices[ident].out_neighbours if not isinstance(node, QuantifierNode) or node.min >= 1], default=0)

                if min_depth < min_depths[ident]:
                    min_depths[ident] = min_depth
                    changed = True

        # Lift the minimal depths of the alternatives to the alternations, where the decision will happen.
        for ident in min_depths:
            if isinstance(self.vertices[ident], AlternationNode):
                assert all(min_depths[node.id] < inf for node in self.vertices[ident].out_neighbours), '{ident} has an alternative that isn\'t reachable.'.format(ident=ident)
                min_depths[ident] = [min_depths[node.id] for node in self.vertices[ident].out_neighbours]

        # Remove the lifted Alternatives and check for infinite derivations.
        for ident in list(min_depths.keys()):
            if isinstance(self.vertices[ident], AlternativeNode):
                del min_depths[ident]
            else:
                assert min_depths[ident] != inf, 'Rule with infinite derivation: %s' % ident

        for ident, min_depth in min_depths.items():
            self.vertices[ident].min_depth = min_depth


class FuzzerGenerator(object):

    def __init__(self, antlr_parser_cls, actions):
        self.antlr_parser_cls = antlr_parser_cls
        self.actions = actions

        self.charset_idx = 0
        self.code_id = 0
        self.alt_idx = 0
        self.quant_idx = 0
        self.rule_name = None

        self.graph = GrammarGraph()

        self.current_start_range = None
        self.token_start_ranges = dict()

        self.labeled_alts = []

    def new_code_id(self, code_type):
        code_name = '{type}_{idx}'.format(type=code_type, idx=self.code_id)
        self.code_id += 1
        return code_name

    def new_charset_name(self):
        charset_name = 'charset_{idx}'.format(idx=self.charset_idx)
        self.charset_idx += 1
        return charset_name

    def find_conditions(self, node):
        if not self.actions:
            return '1'

        if isinstance(node, str):
            return node

        action_block = getattr(node, 'actionBlock', None)
        if action_block:
            if action_block() and action_block().ACTION_CONTENT() and node.QUESTION():
                return ''.join([str(child) for child in action_block().ACTION_CONTENT()])
            return '1'

        element = getattr(node, 'element', None) or getattr(node, 'lexerElement', None)
        if element:
            if not element():
                return '1'
            return self.find_conditions(element(0))

        child_ref = getattr(node, 'alternative', None) or getattr(node, 'lexerElements', None)

        # An alternative can be explicitly empty, in this case it won't have any of the attributes above.
        if not child_ref:
            return '1'

        return self.find_conditions(child_ref())

    @staticmethod
    def character_range_interval(node):
        start = str(node.characterRange().STRING_LITERAL(0))[1:-1]
        end = str(node.characterRange().STRING_LITERAL(1))[1:-1]

        return (int(start.replace('\\u', '0x'), 16) if '\\u' in start else ord(start),
                int(end.replace('\\u', '0x'), 16) if '\\u' in end else ord(end) + 1)

    @staticmethod
    def lexer_charset_interval(src):
        elements = re.split(r'(\w-\w)', src)
        ranges = []
        for element in elements:
            if not element:
                continue

            # Convert character sequences like \n, \t, etc. into a single character.
            element = bytes(element, 'utf-8').decode('unicode_escape')
            if len(element) > 1:
                if element[1] == '-' and len(element) == 3:
                    ranges.append((ord(element[0]), ord(element[2]) + 1))
                else:
                    for char in element:
                        ranges.append((ord(char), ord(char) + 1))
            elif len(element) == 1:
                ranges.append((ord(element), ord(element) + 1))
        return ranges

    def chars_from_set(self, node):
        if node.characterRange():
            return [self.character_range_interval(node)]

        if node.LEXER_CHAR_SET():
            return self.lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])

        if node.STRING_LITERAL():
            assert len(str(node.STRING_LITERAL())) > 2, 'Negated string literal must not be empty.'
            first_char = ord(str(node.STRING_LITERAL())[1])
            return [(first_char, first_char + 1)]

        if node.TOKEN_REF():
            src = str(node.TOKEN_REF())
            assert src in self.token_start_ranges, '{src} not in token_start_ranges.'.format(src=src)
            return self.token_start_ranges[src]

        return []

    def generate(self, lexer_root, parser_root):
        for root in [lexer_root, parser_root]:
            if root:
                self.generate_grammar(root)

        self.graph.calc_min_depths()
        return self.graph

    def generate_grammar(self, node):
        assert isinstance(node, self.antlr_parser_cls.GrammarSpecContext)

        if not self.graph.name:
            self.graph.name = re.sub(r'^(.+?)(Lexer|Parser)?$', r'\1Generator', str(node.identifier().TOKEN_REF() or node.identifier().RULE_REF()))

        if node.prequelConstruct():
            for prequelConstruct in node.prequelConstruct():
                if prequelConstruct.optionsSpec():
                    for option in prequelConstruct.optionsSpec().option():
                        ident = option.identifier()
                        ident = str(ident.RULE_REF() or ident.TOKEN_REF())
                        self.graph.options[ident] = option.optionValue().getText()

                if prequelConstruct.tokensSpec():
                    id_list = prequelConstruct.tokensSpec().idList()
                    if id_list:
                        for identifier in id_list.identifier():
                            assert identifier.TOKEN_REF() is not None, 'Token names must start with uppercase letter.'
                            self.graph.add_node(ImagRuleNode(id=str(identifier.TOKEN_REF())))

                if prequelConstruct.action() and self.actions:
                    action = prequelConstruct.action()
                    action_ident = action.identifier()
                    action_type = str(action_ident.RULE_REF() or action_ident.TOKEN_REF())
                    raw_action_src = ''.join([str(child) for child in action.actionBlock().ACTION_CONTENT()])

                    # We simply append both member and header code chunks to the generated source.
                    # It's the user's responsibility to define them in order.
                    # Both 'member' and 'members' keywords are accepted.
                    if action_type in ('member', 'members'):
                        self.graph.member += raw_action_src
                    elif action_type == 'header':
                        self.graph.header += raw_action_src

        generator_rules = []
        self.graph.add_node(UnlexerRuleNode(id='EOF'))
        for rule in node.rules().ruleSpec():
            if rule.parserRuleSpec():
                self.graph.add_node(UnparserRuleNode(id=str(rule.parserRuleSpec().RULE_REF())))
                generator_rules.append(rule.parserRuleSpec())
            elif rule.lexerRuleSpec():
                self.graph.add_node(UnlexerRuleNode(id=str(rule.lexerRuleSpec().TOKEN_REF())))
                generator_rules.append(rule.lexerRuleSpec())
            else:
                assert False, 'Should not get here.'

        for mode_spec in node.modeSpec():
            for lexer_rule in mode_spec.lexerRuleSpec():
                self.graph.add_node(UnlexerRuleNode(id=str(lexer_rule.TOKEN_REF())))
                generator_rules.append(lexer_rule)

        for rule in generator_rules:
            self.generate_single(rule)

        if node.grammarType().PARSER() or not (node.grammarType().LEXER() or node.grammarType().PARSER()):
            self.graph.default_rule = generator_rules[0].RULE_REF()

    def generate_single(self, node, parent_id=None):
        if isinstance(node, (self.antlr_parser_cls.ParserRuleSpecContext, self.antlr_parser_cls.LexerRuleSpecContext)):
            self.alt_idx, self.quant_idx = 0, 0
            parser_rule = isinstance(node, self.antlr_parser_cls.ParserRuleSpecContext)
            self.rule_name = str(node.RULE_REF() if parser_rule else node.TOKEN_REF())

            # Mark that the next lexerAtom has to be saved as start range.
            if not parser_rule:
                self.current_start_range = []

            rule_block = node.ruleBlock() if parser_rule else node.lexerRuleBlock()
            self.generate_single(rule_block, self.rule_name)

            # Process top-level labeled alternatives of the current rule.
            while self.labeled_alts:
                self.rule_name, children = self.labeled_alts.pop(0)
                for child in children:
                    self.generate_single(child, self.rule_name)

            if not parser_rule:
                self.token_start_ranges[self.rule_name] = self.current_start_range
                self.current_start_range = None

        elif isinstance(node, (self.antlr_parser_cls.RuleAltListContext, self.antlr_parser_cls.AltListContext, self.antlr_parser_cls.LexerAltListContext)):
            children = [child for child in node.children if isinstance(child, ParserRuleContext)]
            if len(children) == 1:
                self.generate_single(children[0], parent_id)
                return

            alt_id = self.rule_name + '_' + str(self.alt_idx)
            self.graph.add_node(AlternationNode(id=alt_id, idx=self.alt_idx, conditions=[self.find_conditions(child) for child in children]))
            self.alt_idx += 1
            self.graph.add_edge(frm=parent_id, to=alt_id)

            for i, child in enumerate(children):
                alternative_id = '{alt_id}_{idx}'.format(alt_id=alt_id, idx=i)
                self.graph.add_node(AlternativeNode(id=alternative_id))
                self.graph.add_edge(frm=alt_id, to=alternative_id)
                self.generate_single(child, alternative_id)

        elif isinstance(node, self.antlr_parser_cls.LabeledAltContext) and node.identifier():
            name = '{rule_name}_{label_name}'.format(rule_name=self.rule_name,
                                                     label_name=(node.identifier().TOKEN_REF() or node.identifier().RULE_REF()).symbol.text)
            self.graph.add_node(UnparserRuleNode(id=name))
            self.graph.add_edge(frm=parent_id, to=name)
            # Notify the alternative that it's a labeled one and should be processed later.
            self.generate_single(node.alternative(), '#' + name)

        # Sequences.
        elif isinstance(node, (self.antlr_parser_cls.AlternativeContext, self.antlr_parser_cls.LexerAltContext)):
            if not node.children:
                lit_id = self.new_code_id('lit')
                self.graph.add_node(LiteralNode(id=lit_id, src=''))
                self.graph.add_edge(parent_id, lit_id)
                return

            if isinstance(node, self.antlr_parser_cls.AlternativeContext):
                children = node.element()
            elif isinstance(node, self.antlr_parser_cls.LexerAltContext):
                children = node.lexerElements().lexerElement()
            else:
                children = []

            if parent_id.startswith('#'):
                # If the current alternative is labeled then it will be processed
                # later since its content goes to a separate method.
                self.labeled_alts.append((parent_id[1:], children))
                return

            for child in children:
                self.generate_single(child, parent_id)

        elif isinstance(node, (self.antlr_parser_cls.ElementContext, self.antlr_parser_cls.LexerElementContext)):
            if node.actionBlock():
                # Conditions are handled at alternative processing.
                if not self.actions or node.QUESTION():
                    self.graph.add_edge(parent_id, 'lambda_0')
                    return

                action_id = self.new_code_id('action')
                self.graph.add_node(ActionNode(id=action_id, src=''.join([str(child) for child in node.actionBlock().ACTION_CONTENT()])))
                self.graph.add_edge(parent_id, action_id)
                return

            suffix = None
            if node.ebnfSuffix():
                suffix = node.ebnfSuffix()
            elif hasattr(node, 'ebnf') and node.ebnf() and node.ebnf().blockSuffix():
                suffix = node.ebnf().blockSuffix().ebnfSuffix()

            if not suffix:
                self.generate_single(node.children[0], parent_id)
                return

            suffix = str(suffix.children[0])
            quant_id = self.new_code_id('quant')
            quant_ranges = {'?': {'min': 0, 'max': 1}, '*': {'min': 0, 'max': 'inf'}, '+': {'min': 1, 'max': 'inf'}}
            self.graph.add_node(QuantifierNode(id=quant_id, idx=self.quant_idx, **quant_ranges[suffix]))
            self.quant_idx += 1
            self.graph.add_edge(frm=parent_id, to=quant_id)
            self.generate_single(node.children[0], quant_id)

        elif isinstance(node, self.antlr_parser_cls.LabeledElementContext):
            self.generate_single(node.atom() or node.block(), parent_id)
            ident = node.identifier()
            name = str(ident.RULE_REF() or ident.TOKEN_REF())
            var_id = self.new_code_id('var')
            self.graph.add_node(VariableNode(var_id, name))
            self.graph.add_edge(parent_id, var_id)
            self.graph.vertices[self.rule_name].has_var = True

        elif isinstance(node, self.antlr_parser_cls.RulerefContext):
            self.graph.add_edge(frm=parent_id, to=str(node.RULE_REF()))

        elif isinstance(node, (self.antlr_parser_cls.LexerAtomContext, self.antlr_parser_cls.AtomContext)):
            if node.DOT():
                lit_id = self.new_code_id('lit')
                self.graph.add_node(LiteralNode(lit_id, any=True))
                self.graph.add_edge(parent_id, lit_id)

            elif node.notSet():
                if node.notSet().setElement():
                    options = self.chars_from_set(node.notSet().setElement())
                else:
                    options = []
                    for set_element in node.notSet().blockSet().setElement():
                        options.extend(self.chars_from_set(set_element))

                charset_id = self.new_charset_name()
                lit_id = self.new_code_id('lit')
                self.graph.charsets.append(Charset(name=charset_id, ranges=sorted(options, key=lambda x: x[0]), invert=True))
                self.graph.add_node(LiteralNode(lit_id, charset=charset_id))
                self.graph.add_edge(parent_id, lit_id)

            elif isinstance(node, self.antlr_parser_cls.LexerAtomContext) and node.characterRange():
                start, end = self.character_range_interval(node)
                if self.current_start_range is not None:
                    self.current_start_range.append((start, end))

                lit_id = self.new_code_id('lit')
                self.graph.add_node(LiteralNode(lit_id, range=[start, end]))
                self.graph.add_edge(parent_id, lit_id)

            elif isinstance(node, self.antlr_parser_cls.LexerAtomContext) and node.LEXER_CHAR_SET():
                ranges = self.lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])

                if self.current_start_range is not None:
                    self.current_start_range.extend(ranges)

                charset_id = self.new_charset_name()
                lit_id = self.new_code_id('lit')
                self.graph.charsets.append(Charset(name=charset_id, ranges=sorted(ranges, key=lambda x: x[0])))
                self.graph.add_node(LiteralNode(lit_id, charset=charset_id))
                self.graph.add_edge(parent_id, lit_id)

            for child in node.children:
                self.generate_single(child, parent_id)

        elif isinstance(node, self.antlr_parser_cls.TerminalContext):
            if node.TOKEN_REF():
                self.graph.add_edge(frm=parent_id, to=str(node.TOKEN_REF()))

            elif node.STRING_LITERAL():
                src = str(node.STRING_LITERAL())[1:-1]
                if self.current_start_range is not None:
                    self.current_start_range.append((ord(src[0]), ord(src[0]) + 1))
                lit_id = self.new_code_id('lit')
                self.graph.add_node(LiteralNode(lit_id, src=src))
                self.graph.add_edge(parent_id, lit_id)

        elif isinstance(node, ParserRuleContext) and node.getChildCount():
            for child in node.children:
                self.generate_single(child, parent_id)


class FuzzerFactory(object):
    """
    Class that generates fuzzers from grammars.
    """
    def __init__(self, lang, work_dir=None, antlr=default_antlr_path):
        """
        :param lang: Language of the generated code.
        :param work_dir: Directory to generate fuzzers into.
        :param antlr: Path to the ANTLR jar.
        """
        self.lang = lang
        env = Environment(trim_blocks=True,
                          lstrip_blocks=True,
                          keep_trailing_newline=False)
        env.filters['substitute'] = lambda s, frm, to: re.sub(frm, to, str(s))
        self.template = env.from_string(get_data(__package__, join('resources', 'codegen', 'GeneratorTemplate.' + lang + '.jinja')).decode('utf-8'))
        self.work_dir = work_dir or getcwd()

        antlr_dir = join(self.work_dir, 'antlr')
        makedirs(antlr_dir, exist_ok=True)

        # Copy the grammars from the package to the given working directory.
        antlr_resources = ['ANTLRv4Lexer.g4', 'ANTLRv4Parser.g4', 'LexBasic.g4', 'LexerAdaptor.py']
        for resource in antlr_resources:
            with open(join(antlr_dir, resource), 'wb') as f:
                f.write(get_data(__package__, join('resources', 'antlr', resource)))

        self.antlr_lexer_cls, self.antlr_parser_cls, _ = build_grammars(antlr_resources, antlr_dir, antlr=antlr)

    def generate_fuzzer(self, grammars, *, encoding='utf-8', lib_dir=None, actions=True, pep8=False):
        """
        Generates fuzzers from grammars.

        :param grammars: List of grammar files to generate from.
        :param encoding: Grammar file encoding.
        :param lib_dir: Alternative directory to look for imports.
        :param actions: Boolean to enable or disable grammar actions.
        :param pep8: Boolean to enable pep8 to beautify the generated fuzzer source.
        """
        lexer_root, parser_root = None, None

        for grammar in grammars:
            root = self._parse(grammar, encoding, lib_dir)
            # Lexer and/or combined grammars are processed first to evaluate TOKEN_REF-s.
            if root.grammarType().LEXER() or not root.grammarType().PARSER():
                lexer_root = root
            else:
                parser_root = root

        graph = FuzzerGenerator(self.antlr_parser_cls, actions).generate(lexer_root, parser_root)
        src = self.template.render(graph=graph, version=__version__).lstrip()
        with open(join(self.work_dir, graph.name + '.' + self.lang), 'w') as f:
            if pep8:
                src = autopep8.fix_code(src)
            f.write(src)

    @staticmethod
    def _collect_imports(root, base_dir, lib_dir):
        imports = set()
        for prequel in root.prequelConstruct():
            if prequel.delegateGrammars():
                for delegate_grammar in prequel.delegateGrammars().delegateGrammar():
                    ident = delegate_grammar.identifier(0)
                    grammar_fn = str(ident.RULE_REF() or ident.TOKEN_REF()) + '.g4'
                    if lib_dir is not None and exists(join(lib_dir, grammar_fn)):
                        imports.add(join(lib_dir, grammar_fn))
                    else:
                        imports.add(join(base_dir, grammar_fn))
        return imports

    def _parse(self, grammar, encoding, lib_dir):
        work_list = {grammar}
        root = None

        while work_list:
            grammar = work_list.pop()

            antlr_parser = self.antlr_parser_cls(CommonTokenStream(self.antlr_lexer_cls(FileStream(grammar, encoding=encoding))))
            current_root = antlr_parser.grammarSpec()
            # assert antlr_parser._syntaxErrors > 0, 'Parse error in ANTLR grammar.'

            # Save the 'outermost' grammar.
            if not root:
                root = current_root
            else:
                # Unite the rules of the imported grammar with the host grammar's rules.
                for rule in current_root.rules().ruleSpec():
                    root.rules().addChild(rule)

            work_list |= self._collect_imports(current_root, dirname(grammar), lib_dir)

        return root


def execute():
    parser = ArgumentParser(description='Grammarinator: Processor', epilog="""
        The tool processes a grammar in ANTLR v4 format (*.g4, either separated
        to lexer and parser grammar files, or a single combined grammar) and
        creates a fuzzer that can generate randomized content conforming to
        the format described by the grammar.
        """)
    parser.add_argument('grammar', metavar='FILE', nargs='+',
                        help='ANTLR grammar files describing the expected format to generate.')
    parser.add_argument('--language', choices=['py'], default='py',
                        help='language of the generated code (choices: %(choices)s; default: %(default)s)')
    parser.add_argument('--no-actions', dest='actions', default=True, action='store_false',
                        help='do not process inline actions.')
    parser.add_argument('--encoding', metavar='ENC', default='utf-8',
                        help='grammar file encoding (default: %(default)s).')
    parser.add_argument('--lib', metavar='DIR',
                        help='alternative location of import grammars.')
    parser.add_argument('--pep8', default=False, action='store_true',
                        help='enable autopep8 to format the generated fuzzer.')
    parser.add_argument('-o', '--out', metavar='DIR', default=getcwd(),
                        help='temporary working directory (default: %(default)s).')
    add_disable_cleanup_argument(parser)
    add_antlr_argument(parser)
    add_log_level_argument(parser)
    add_version_argument(parser)
    args = parser.parse_args()

    for grammar in args.grammar:
        if not exists(grammar):
            parser.error('{grammar} does not exist.'.format(grammar=grammar))

    process_log_level_argument(args)
    process_antlr_argument(args)

    FuzzerFactory(args.language, args.out, args.antlr).generate_fuzzer(args.grammar, encoding=args.encoding, lib_dir=args.lib, actions=args.actions, pep8=args.pep8)

    if args.cleanup:
        rmtree(join(args.out, 'antlr'), ignore_errors=True)


if __name__ == '__main__':
    execute()
