# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import re

from argparse import ArgumentParser
from collections import defaultdict, OrderedDict
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

    _cnt = 0

    def __init__(self, id=None):
        if id is None:
            id = Node._cnt
            Node._cnt += 1
        self.id = id
        self.out_neighbours = []
        self.min_depth = inf


class RuleNode(Node):

    def __init__(self, name, label, type):
        super().__init__(name if label is None else '_'.join((name, label)))
        self.name = name
        self.type = type
        self.has_var = False


class UnlexerRuleNode(RuleNode):

    def __init__(self, name):
        super().__init__(name, None, 'UnlexerRule')
        self.start_ranges = None


class UnparserRuleNode(RuleNode):

    def __init__(self, name, label=None):
        super().__init__(name, label, 'UnparserRule')


class ImagRuleNode(Node):

    def __init__(self, id):
        super().__init__(id)


class LiteralNode(Node):

    def __init__(self, src=None, charset=None, range=None, any=False):
        super().__init__()
        self.src = src
        self.charset = charset
        self.range = range
        self.any_char = any


class LambdaNode(Node):

    def __init__(self):
        super().__init__()


class AlternationNode(Node):

    def __init__(self, idx, conditions):
        super().__init__()
        self.idx = idx
        self.conditions = conditions


class AlternativeNode(Node):

    def __init__(self):
        super().__init__()


class QuantifierNode(Node):

    def __init__(self, idx, min, max):
        super().__init__()
        self.idx = idx
        self.min = min
        self.max = max


class ActionNode(Node):

    def __init__(self, src):
        super().__init__()
        self.src = src


class VariableNode(Node):

    def __init__(self, name):
        super().__init__()
        self.name = name


class Charset(object):

    _cnt = 0

    def __init__(self, ranges, invert=False):
        self.name = 'charset_{idx}'.format(idx=Charset._cnt)
        Charset._cnt += 1
        self.ranges = ranges
        self.invert = invert


class GrammarGraph(object):

    def __init__(self):
        self.name = None
        self.vertices = OrderedDict()
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
        return node.id

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
                min_depth = selector((min_depths[node.id] + int(isinstance(self.vertices[node.id], RuleNode))
                                      for node in self.vertices[ident].out_neighbours if not isinstance(node, QuantifierNode) or node.min >= 1), default=0)

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


def build_graph(antlr_parser_cls, actions, lexer_root, parser_root):

    def find_conditions(node):
        if not actions:
            return '1'

        if isinstance(node, str):
            return node

        action_block = getattr(node, 'actionBlock', None)
        if action_block:
            if action_block() and action_block().ACTION_CONTENT() and node.QUESTION():
                return ''.join(str(child) for child in action_block().ACTION_CONTENT())
            return '1'

        element = getattr(node, 'element', None) or getattr(node, 'lexerElement', None)
        if element:
            if not element():
                return '1'
            return find_conditions(element(0))

        child_ref = getattr(node, 'alternative', None) or getattr(node, 'lexerElements', None)

        # An alternative can be explicitly empty, in this case it won't have any of the attributes above.
        if not child_ref:
            return '1'

        return find_conditions(child_ref())

    def character_range_interval(node):
        start = str(node.characterRange().STRING_LITERAL(0))[1:-1]
        end = str(node.characterRange().STRING_LITERAL(1))[1:-1]

        return (int(start.replace('\\u', '0x'), 16) if '\\u' in start else ord(start),
                int(end.replace('\\u', '0x'), 16) if '\\u' in end else ord(end) + 1)

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

    def chars_from_set(node):
        if node.characterRange():
            return [character_range_interval(node)]

        if node.LEXER_CHAR_SET():
            return lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])

        if node.STRING_LITERAL():
            assert len(str(node.STRING_LITERAL())) > 2, 'Negated string literal must not be empty.'
            first_char = ord(str(node.STRING_LITERAL())[1])
            return [(first_char, first_char + 1)]

        if node.TOKEN_REF():
            src = str(node.TOKEN_REF())
            assert graph.vertices[src].start_ranges is not None, '{src} has no character start ranges.'.format(src=src)
            return graph.vertices[src].start_ranges

        return []

    def build_rule(rule, node):
        lexer_rule = isinstance(rule, UnlexerRuleNode)
        alt_idx, quant_idx = 0, 0  # pylint: disable=unused-variable

        def build_expr(node, parent_id):
            if isinstance(node, (antlr_parser_cls.RuleAltListContext, antlr_parser_cls.AltListContext, antlr_parser_cls.LexerAltListContext)):
                children = [child for child in node.children if isinstance(child, ParserRuleContext)]
                if len(children) == 1:
                    build_expr(children[0], parent_id)
                    return

                nonlocal alt_idx
                alt_id = graph.add_node(AlternationNode(idx=alt_idx, conditions=[find_conditions(child) for child in children]))
                alt_idx += 1
                graph.add_edge(frm=parent_id, to=alt_id)

                for child in children:
                    alternative_id = graph.add_node(AlternativeNode())
                    graph.add_edge(frm=alt_id, to=alternative_id)
                    build_expr(child, alternative_id)

            elif isinstance(node, antlr_parser_cls.LabeledAltContext):
                if not node.identifier():
                    build_expr(node.alternative(), parent_id)
                    return

                rule_node = UnparserRuleNode(name=rule.name, label=str(node.identifier().TOKEN_REF() or node.identifier().RULE_REF()))
                graph.add_edge(frm=parent_id, to=graph.add_node(rule_node))
                build_rule(rule_node, node.alternative())

            elif isinstance(node, (antlr_parser_cls.AlternativeContext, antlr_parser_cls.LexerAltContext)):
                if not node.children:
                    graph.add_edge(frm=parent_id, to=lambda_id)
                    return

                for child in node.element() if isinstance(node, antlr_parser_cls.AlternativeContext) else node.lexerElements().lexerElement():
                    build_expr(child, parent_id)

            elif isinstance(node, (antlr_parser_cls.ElementContext, antlr_parser_cls.LexerElementContext)):
                if node.actionBlock():
                    # Conditions are handled at alternative processing.
                    if not actions or node.QUESTION():
                        graph.add_edge(frm=parent_id, to=lambda_id)
                        return

                    graph.add_edge(frm=parent_id, to=graph.add_node(ActionNode(src=''.join(str(child) for child in node.actionBlock().ACTION_CONTENT()))))
                    return

                suffix = None
                if node.ebnfSuffix():
                    suffix = node.ebnfSuffix()
                elif hasattr(node, 'ebnf') and node.ebnf() and node.ebnf().blockSuffix():
                    suffix = node.ebnf().blockSuffix().ebnfSuffix()

                if not suffix:
                    build_expr(node.children[0], parent_id)
                    return

                nonlocal quant_idx
                suffix = str(suffix.children[0])
                quant_ranges = {'?': {'min': 0, 'max': 1}, '*': {'min': 0, 'max': 'inf'}, '+': {'min': 1, 'max': 'inf'}}
                quant_id = graph.add_node(QuantifierNode(idx=quant_idx, **quant_ranges[suffix]))
                quant_idx += 1
                graph.add_edge(frm=parent_id, to=quant_id)
                build_expr(node.children[0], quant_id)

            elif isinstance(node, antlr_parser_cls.LabeledElementContext):
                build_expr(node.atom() or node.block(), parent_id)
                ident = node.identifier()
                name = str(ident.RULE_REF() or ident.TOKEN_REF())
                graph.add_edge(frm=parent_id, to=graph.add_node(VariableNode(name=name)))
                rule.has_var = True

            elif isinstance(node, antlr_parser_cls.RulerefContext):
                graph.add_edge(frm=parent_id, to=str(node.RULE_REF()))

            elif isinstance(node, (antlr_parser_cls.LexerAtomContext, antlr_parser_cls.AtomContext)):
                if node.DOT():
                    graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(any=True)))

                elif node.notSet():
                    if node.notSet().setElement():
                        options = chars_from_set(node.notSet().setElement())
                    else:
                        options = []
                        for set_element in node.notSet().blockSet().setElement():
                            options.extend(chars_from_set(set_element))

                    charset = Charset(ranges=sorted(options, key=lambda x: x[0]), invert=True)
                    graph.charsets.append(charset)
                    graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(charset=charset.name)))

                elif isinstance(node, antlr_parser_cls.LexerAtomContext) and node.characterRange():
                    start, end = character_range_interval(node)
                    if lexer_rule:
                        rule.start_ranges.append((start, end))

                    graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(range=[start, end])))

                elif isinstance(node, antlr_parser_cls.LexerAtomContext) and node.LEXER_CHAR_SET():
                    ranges = lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])
                    if lexer_rule:
                        rule.start_ranges.extend(ranges)

                    charset = Charset(ranges=sorted(ranges, key=lambda x: x[0]))
                    graph.charsets.append(charset)
                    graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(charset=charset.name)))

                for child in node.children:
                    build_expr(child, parent_id)

            elif isinstance(node, antlr_parser_cls.TerminalContext):
                if node.TOKEN_REF():
                    graph.add_edge(frm=parent_id, to=str(node.TOKEN_REF()))

                elif node.STRING_LITERAL():
                    src = str(node.STRING_LITERAL())[1:-1]
                    if lexer_rule:
                        rule.start_ranges.append((ord(src[0]), ord(src[0]) + 1))

                    graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(src=src)))

            elif isinstance(node, ParserRuleContext) and node.getChildCount():
                for child in node.children:
                    build_expr(child, parent_id)

        if lexer_rule:
            rule.start_ranges = []

        build_expr(node, rule.id)

    def build_grammar(node):
        assert isinstance(node, antlr_parser_cls.GrammarSpecContext)

        if not graph.name:
            graph.name = re.sub(r'^(.+?)(Lexer|Parser)?$', r'\1Generator', str(node.identifier().TOKEN_REF() or node.identifier().RULE_REF()))

        for prequelConstruct in node.prequelConstruct() if node.prequelConstruct() else ():
            for option in prequelConstruct.optionsSpec().option() if prequelConstruct.optionsSpec() else ():
                ident = option.identifier()
                ident = str(ident.RULE_REF() or ident.TOKEN_REF())
                graph.options[ident] = option.optionValue().getText()

            for identifier in prequelConstruct.tokensSpec().idList().identifier() if prequelConstruct.tokensSpec() and prequelConstruct.tokensSpec().idList() else ():
                assert identifier.TOKEN_REF() is not None, 'Token names must start with uppercase letter.'
                graph.add_node(ImagRuleNode(id=str(identifier.TOKEN_REF())))

            if prequelConstruct.action() and actions:
                action = prequelConstruct.action()
                action_ident = action.identifier()
                action_type = str(action_ident.RULE_REF() or action_ident.TOKEN_REF())
                raw_action_src = ''.join(str(child) for child in action.actionBlock().ACTION_CONTENT())

                # We simply append both member and header code chunks to the generated source.
                # It's the user's responsibility to define them in order.
                # Both 'member' and 'members' keywords are accepted.
                if action_type in ('member', 'members'):
                    graph.member += raw_action_src
                elif action_type == 'header':
                    graph.header += raw_action_src

        generator_rules = []
        graph.add_node(UnlexerRuleNode(name='EOF'))
        for rule in node.rules().ruleSpec():
            if rule.parserRuleSpec():
                rule_spec = rule.parserRuleSpec()
                rule_node = UnparserRuleNode(name=str(rule_spec.RULE_REF()))
                graph.add_node(rule_node)
                generator_rules.append((rule_node, rule_spec.ruleBlock()))
            elif rule.lexerRuleSpec():
                rule_spec = rule.lexerRuleSpec()
                rule_node = UnlexerRuleNode(name=str(rule_spec.TOKEN_REF()))
                graph.add_node(rule_node)
                generator_rules.append((rule_node, rule_spec.lexerRuleBlock()))
            else:
                assert False, 'Should not get here.'

        for mode_spec in node.modeSpec():
            for rule_spec in mode_spec.lexerRuleSpec():
                rule_node = UnlexerRuleNode(name=str(rule_spec.TOKEN_REF()))
                graph.add_node(rule_node)
                generator_rules.append((rule_node, rule_spec.lexerRuleBlock()))

        for rule_args in generator_rules:
            build_rule(*rule_args)

        if node.grammarType().PARSER() or not (node.grammarType().LEXER() or node.grammarType().PARSER()):
            graph.default_rule = generator_rules[0][0].name

    graph = GrammarGraph()
    lambda_id = graph.add_node(LambdaNode())

    for root in [lexer_root, parser_root]:
        if root:
            build_grammar(root)

    graph.calc_min_depths()
    return graph


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

    def generate_fuzzer(self, grammars, *, options=None, encoding='utf-8', lib_dir=None, actions=True, pep8=False):
        """
        Generates fuzzers from grammars.

        :param grammars: List of grammar files to generate from.
        :param options: Dictionary of options that override/extend those set in the grammar.
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

        graph = build_graph(self.antlr_parser_cls, actions, lexer_root, parser_root)
        graph.options.update(options or {})

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
    parser.add_argument('-D', metavar='OPT=VAL', dest='options', default=list(), action='append',
                        help='set/override grammar-level option')
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

    options = dict()
    for option in args.options:
        parts = re.fullmatch('([^=]+)=(.*)', option)
        if not parts:
            parser.error('option not in OPT=VAL format: {option}'.format(option=option))

        name, value = parts.group(1, 2)
        options[name] = value

    process_log_level_argument(args)
    process_antlr_argument(args)

    FuzzerFactory(args.language, args.out, args.antlr).generate_fuzzer(args.grammar, options=options, encoding=args.encoding, lib_dir=args.lib, actions=args.actions, pep8=args.pep8)

    if args.cleanup:
        rmtree(join(args.out, 'antlr'), ignore_errors=True)


if __name__ == '__main__':
    execute()
