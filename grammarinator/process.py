# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import antlerinator
import autopep8
import logging
import re
import sys

from antlr4 import CommonTokenStream, FileStream, ParserRuleContext
from argparse import ArgumentParser
from collections import defaultdict
from contextlib import contextmanager
from os.path import dirname, exists, join
from os import getcwd, makedirs

from .parser_builder import build_grammars
from .pkgdata import __version__, default_antlr_path
from .runtime.tree import *

logger = logging.getLogger('grammarinator')
logging.basicConfig(format='%(message)s')


class Node(object):

    def __init__(self, id):
        self.id = id
        self.out_neighbours = []


class RuleNode(Node):
    pass


class AlternationNode(Node):
    pass


class AlternativeNode(Node):
    pass


class QuantifierNode(Node):
    pass


class GrammarGraph(object):

    def __init__(self):
        self.vertices = dict()
        self.alt_id = 0
        self.quant_id = 0

    def new_alt_id(self):
        alt_name = 'alt_{idx}'.format(idx=self.alt_id)
        self.alt_id += 1
        return alt_name

    def new_quant_id(self):
        quant_name = 'quant_{idx}'.format(idx=self.quant_id)
        self.quant_id += 1
        return quant_name

    def add_node(self, node):
        self.vertices[node.id] = node

    def add_edge(self, frm, to):
        assert frm in self.vertices, '{frm} not in vertices.'.format(frm=frm)
        assert to in self.vertices, '{to} not in vertices.'.format(to=to)
        self.vertices[frm].out_neighbours.append(self.vertices[to])

    def calc_min_depths(self):
        min_depths = defaultdict(lambda: float('inf'))
        changed = True

        while changed:
            changed = False
            for ident in self.vertices:
                selector = min if isinstance(self.vertices[ident], AlternationNode) else max
                min_depth = selector([min_depths[node.id] + int(isinstance(self.vertices[node.id], RuleNode))
                                      for node in self.vertices[ident].out_neighbours if not isinstance(node, QuantifierNode)], default=0)

                if min_depth < min_depths[ident]:
                    min_depths[ident] = min_depth
                    changed = True

        # Lift the minimal depths of the alternatives to the alternations, where the decision will happen.
        for ident in min_depths:
            if isinstance(self.vertices[ident], AlternationNode):
                assert all(min_depths[node.id] < float('inf') for node in self.vertices[ident].out_neighbours), '{ident} has an alternative that isn\'t reachable.'.format(ident=ident)
                min_depths[ident] = [min_depths[node.id] for node in self.vertices[ident].out_neighbours]

        # The lifted Alternatives aren't needed anymore.
        for ident in list(min_depths.keys()):
            if isinstance(self.vertices[ident], AlternativeNode):
                del min_depths[ident]

        return min_depths


class FuzzerGenerator(object):

    def __init__(self, parser, actions):
        self.parser = parser
        self.actions = actions

        self.indent_level = 0
        self.charset_idx = 0

        self.graph = GrammarGraph()

        self.current_start_range = None
        self.token_start_ranges = dict()

        self.lexer_header = ''
        self.lexer_body = ''
        self.lexer_name = None
        self.parser_header = ''
        self.parser_body = ''
        self.parser_name = None

    @contextmanager
    def indent(self):
        self.indent_level += 4
        yield
        self.indent_level -= 4

    def line(self, src):
        return (' ' * self.indent_level) + src + '\n'

    def new_charset_name(self):
        charset_name = 'charset_{idx}'.format(idx=self.charset_idx)
        self.charset_idx += 1
        return charset_name

    def create_header(self, grammar_name, grammar_type):
        lexer = grammar_type == 'lexer'
        fuzzer_name = '{grammar_name}Un{grammar_type}'.format(
            grammar_name=grammar_name,
            grammar_type=grammar_type)

        src = self.line('# Generated by Grammarinator {version}\n'.format(version=__version__))
        src += self.line('from itertools import chain')
        src += self.line('from grammarinator.runtime import *\n')

        if lexer:
            self.lexer_header += src
        else:
            self.parser_header += src

        src = self.line('class {fuzzer_name}(Grammarinator):\n'.format(fuzzer_name=fuzzer_name))
        with self.indent():
            src += self.line('def __init__(self{args}):'.format(args='' if lexer else ', lexer'))

            with self.indent():
                src += self.line('super({fuzzer_name}, self).__init__()'.format(fuzzer_name=fuzzer_name))
                src += self.line('self.lexer = {lexer_ref}'.format(lexer_ref='self' if lexer else 'lexer'))
                src += self.line('self.set_options()\n')

        if lexer:
            self.lexer_body += src
            with self.indent():
                self.lexer_body += self.line('def EOF(self, *args, **kwargs):')
                with self.indent():
                    self.lexer_body += self.line('pass\n')
        else:
            self.parser_body += self.line('import {lexer_name}'.format(lexer_name=self.lexer_name))
            self.parser_body += src

        return fuzzer_name

    def init_fuzzer(self, grammar_name, lexer_fuzzer, parser_fuzzer):
        if not (lexer_fuzzer or parser_fuzzer):
            lexer_fuzzer, parser_fuzzer = True, True

        if lexer_fuzzer:
            self.lexer_name = self.create_header(grammar_name, 'lexer')
        if parser_fuzzer:
            self.parser_name = self.create_header(grammar_name, 'parser')

    def find_conditions(self, node):
        if not self.actions:
            return '1'

        if type(node) == str:
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

    def character_range_interval(self, node):
        start = str(node.characterRange().STRING_LITERAL(0))[1:-1]
        end = str(node.characterRange().STRING_LITERAL(1))[1:-1]

        return int(start.replace('\\u', '0x'), 16) if '\\u' in start else ord(start),\
               int(end.replace('\\u', '0x'), 16) if '\\u' in end else ord(end) + 1

    def lexer_charset_interval(self, src):
        elements = re.split('(\w-\w)', src)
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

    def generate(self, lexer_root, parser_root):
        all_lexer_ids, all_parser_ids = [], []
        for root in [lexer_root, parser_root]:
            if root:
                lexer_ids, parser_ids = self.generate_grammar(root)
                all_lexer_ids.extend(lexer_ids)
                all_parser_ids.extend(parser_ids)

        self.generate_depths(all_lexer_ids, all_parser_ids)

        return [
            (self.lexer_name, self.lexer_header + '\n\n' + self.lexer_body),
            (self.parser_name, self.parser_header + '\n\n' + self.parser_body),
        ]

    def generate_grammar(self, node):
        assert isinstance(node, self.parser.GrammarSpecContext)
        name_token = node.identifier().TOKEN_REF() or node.identifier().RULE_REF()
        self.init_fuzzer(str(name_token).replace('Parser', '').replace('Lexer', ''),
                         node.grammarType().LEXER(), node.grammarType().PARSER())

        if node.prequelConstruct():
            for prequelConstruct in node.prequelConstruct():
                if prequelConstruct.optionsSpec():
                    option_spec = prequelConstruct.optionsSpec()
                    options = []
                    for option in option_spec.option():
                        ident = option.identifier()
                        options.append('{name}="{value}"'.format(name=ident.RULE_REF() or ident.TOKEN_REF(),
                                                                 value=option.optionValue().getText()))

                    with self.indent():
                        set_options = self.line('def set_options(self):')
                        with self.indent():
                            set_options += self.line('self.options = dict({options})\n'.format(options=', '.join(options)))

                    if self.lexer_body:
                        self.lexer_body += set_options
                    if self.parser_body:
                        self.parser_body += set_options

                elif prequelConstruct.action() and self.actions:
                    action = prequelConstruct.action()
                    scope_name = action.actionScopeName()
                    if scope_name:
                        action_scope = scope_name.LEXER() or scope_name.PARSER()
                        assert action_scope, '{scope} scope not supported.'.format(scope=scope_name.identifier().RULE_REF() or scope_name.identifier().TOKEN_REF())
                        action_scope = str(action_scope)
                    else:
                        action_scope = 'parser'

                    action_ident = action.identifier()
                    action_type = str(action_ident.RULE_REF() or action_ident.TOKEN_REF())
                    raw_action_src = ''.join([str(child) for child in action.actionBlock().ACTION_CONTENT()])

                    if action_type == 'header':
                        action_src = raw_action_src
                    else:
                        with self.indent():
                            action_src = ''.join([self.line(line) for line in raw_action_src.splitlines()])

                    # We simply append both member and header code chunks to the generated source.
                    # It's the user's responsibility to define them in order.
                    if action_scope == 'parser':
                        # Both 'member' and 'members' keywords are accepted.
                        if action_type.startswith('member'):
                            self.parser_body += action_src
                        elif action_type == 'header':
                            self.parser_header += action_src
                    elif action_scope == 'lexer':
                        if action_type.startswith('member'):
                            self.lexer_body += action_src
                        elif action_type == 'header':
                            self.lexer_header += action_src

        rules = node.rules().ruleSpec()
        lexer_ids, parser_ids = [], []
        lexer_rules, parser_rules = [], []
        self.graph.add_node(RuleNode(id='EOF'))
        for rule in rules:
            if rule.parserRuleSpec():
                name = str(rule.parserRuleSpec().RULE_REF())
                self.graph.add_node(RuleNode(id=name))
                parser_rules.append(rule.parserRuleSpec())
                parser_ids.append(name)
            elif rule.lexerRuleSpec():
                name = str(rule.lexerRuleSpec().TOKEN_REF())
                self.graph.add_node(RuleNode(id=name))
                lexer_rules.append(rule.lexerRuleSpec())
                lexer_ids.append(name)
            else:
                assert False, 'Should not get here.'

        for mode_spec in node.modeSpec():
            for lexer_rule in mode_spec.lexerRuleSpec():
                name = str(lexer_rule.TOKEN_REF())
                self.graph.add_node(RuleNode(id=name))
                lexer_rules.append(lexer_rule)
                lexer_ids.append(name)

        with self.indent():
            for rule in lexer_rules:
                self.lexer_body += self.generate_single(rule, None, lexer_ids)
            for rule in parser_rules:
                self.parser_body += self.generate_single(rule, None, parser_ids)

        return lexer_ids, parser_ids

    def generate_single(self, node, parent_id, new_alt_ids):

        if isinstance(node, (self.parser.ParserRuleSpecContext, self.parser.LexerRuleSpecContext)):
            parser_rule = isinstance(node, self.parser.ParserRuleSpecContext)
            node_type = UnparserRule if parser_rule else UnlexerRule
            rule_name = str(node.RULE_REF() if parser_rule else node.TOKEN_REF())

            # Mark that the next lexerAtom has to be saved as start range.
            if not parser_rule:
                self.current_start_range = []

            rule_header = self.line('def {rule_name}(self, *, max_depth=float(\'inf\')):'.format(rule_name=rule_name))
            with self.indent():
                local_ctx = self.line('local_ctx = dict()')
                rule_code = self.line('current = self.create_node({node_type}(name=\'{rule_name}\'))'.format(node_type=node_type.__name__,
                                                                                                             rule_name=rule_name))
                rule_block = node.ruleBlock() if parser_rule else node.lexerRuleBlock()
                rule_code += self.generate_single(rule_block, rule_name, new_alt_ids)
                rule_code += self.line('return current\n')

            # local_ctx only has to be initialized if we have variable assignment.
            rule_code = rule_header + (local_ctx if 'local_ctx' in rule_code else '') + rule_code

            if not parser_rule:
                self.token_start_ranges[rule_name] = self.current_start_range
                self.current_start_range = None

            return rule_code

        if isinstance(node, (self.parser.RuleAltListContext, self.parser.AltListContext, self.parser.LexerAltListContext)):
            children = [child for child in node.children if isinstance(child, ParserRuleContext)]
            if len(children) == 1:
                return self.generate_single(children[0], parent_id, new_alt_ids)

            alt_name = self.graph.new_alt_id()
            new_alt_ids.append(alt_name)
            self.graph.add_node(AlternationNode(id=alt_name))
            self.graph.add_edge(frm=parent_id, to=alt_name)

            result = self.line('weights = self.depth_limited_weights([{weights}], self.min_depths[\'{alt_name}\'], max_depth)'.format(
                                weights=', '.join([self.find_conditions(child) for child in children]),
                                alt_name=alt_name))
            result += self.line('choice = self.choice(weights)'.format(max=len(children)))
            for i, child in enumerate(children):
                alternative_name = '{alt_name}_{idx}'.format(alt_name=alt_name, idx=i)
                self.graph.add_node(AlternativeNode(id=alternative_name))
                self.graph.add_edge(frm=alt_name, to=alternative_name)

                result += self.line('{if_kw} choice == {idx}:'.format(if_kw='if' if i == 0 else 'elif', idx=i))
                with self.indent():
                    result += self.generate_single(child, alternative_name, new_alt_ids) or self.line('pass')
            return result

        # Sequences.
        if isinstance(node, (self.parser.AlternativeContext, self.parser.LexerAltContext)):
            if not node.children:
                return self.line('current += UnlexerRule(src=\'\')')

            if isinstance(node, self.parser.AlternativeContext):
                children = node.element()
            elif isinstance(node, self.parser.LexerAltContext):
                children = node.lexerElements().lexerElement()
            else:
                children = []
            return ''.join([self.generate_single(child, parent_id, new_alt_ids) for child in children])

        if isinstance(node, (self.parser.ElementContext, self.parser.LexerElementContext)):
            if self.actions and node.actionBlock():
                # Conditions are handled at alternative processing.
                if node.QUESTION():
                    return ''

                action_src = ''.join([str(child) for child in node.actionBlock().ACTION_CONTENT()])
                action_src = re.sub('\$(?P<var_name>\w+)', 'local_ctx[\'\g<var_name>\']', action_src)

                return ''.join([self.line(line) for line in action_src.splitlines()])

            suffix = None
            if node.ebnfSuffix():
                suffix = node.ebnfSuffix()
            elif hasattr(node, 'ebnf') and node.ebnf() and node.ebnf().blockSuffix():
                suffix = node.ebnf().blockSuffix().ebnfSuffix()

            if not suffix:
                return self.generate_single(node.children[0], parent_id, new_alt_ids)

            suffix = str(suffix.children[0])

            if suffix in ['?', '*']:
                quant_name = self.graph.new_quant_id()
                self.graph.add_node(QuantifierNode(id=quant_name))
                self.graph.add_edge(frm=parent_id, to=quant_name)
                new_alt_ids.append(quant_name)
                parent_id = quant_name

            quant_type = {'?': 'zero_or_one', '*': 'zero_or_more', '+': 'one_or_more'}[suffix]
            result = self.line('if max_depth >= {min_depth}:'.format(min_depth='0' if suffix == '+' else 'self.min_depths[\'{name}\']'.format(name=parent_id)))
            with self.indent():
                result += self.line('for _ in self.{quant_type}(max_depth=max_depth):'.format(quant_type=quant_type))

                with self.indent():
                    result += self.generate_single(node.children[0], parent_id, new_alt_ids)
                result += '\n'
            return result

        if isinstance(node, self.parser.LabeledElementContext):
            ident = node.identifier()
            name = ident.RULE_REF() or ident.TOKEN_REF()
            result = self.generate_single(node.atom() or node.block(), parent_id, new_alt_ids)
            result += self.line('local_ctx[\'{name}\'] = current.last_child'.format(name=name))
            return result

        if isinstance(node, self.parser.RulerefContext):
            self.graph.add_edge(frm=parent_id, to=str(node.RULE_REF()))
            return self.line('current += self.{rule_name}(max_depth=max_depth - 1)'.format(rule_name=node.RULE_REF()))

        if isinstance(node, (self.parser.LexerAtomContext, self.parser.AtomContext)):
            if node.DOT():
                return self.line('current += UnlexerRule(src=self.any_char())')

            if node.notSet():
                if node.notSet().setElement():
                    options = self.chars_from_set(node.notSet().setElement())
                else:
                    options = []
                    for set_element in node.notSet().blockSet().setElement():
                        options.extend(self.chars_from_set(set_element))

                charset_name = self.new_charset_name()
                self.lexer_header += '{charset_name} = list(chain(*multirange_diff(printable_unicode_ranges, [{charset}])))\n'.format(charset_name=charset_name, charset=','.join(['({start}, {end})'.format(start=chr_range[0], end=chr_range[1]) for chr_range in sorted(options, key=lambda x: x[0])]))
                charset_ref = charset_name if isinstance(node, self.parser.LexerAtomContext) else '{lexer_name}.{charset_name}'.format(lexer_name=self.lexer_name, charset_name=charset_name)
                return self.line('current += UnlexerRule(src=self.char_from_list({charset_ref}))'.format(charset_ref=charset_ref))

            if isinstance(node, self.parser.LexerAtomContext):
                if node.characterRange():
                    start, end = self.character_range_interval(node)
                    if self.current_start_range is not None:
                        self.current_start_range.append((start, end))
                    return self.line('current += self.create_node(UnlexerRule(src=self.char_from_list(range({start}, {end}))))'.format(start=start, end=end))

                if node.LEXER_CHAR_SET():
                    ranges = self.lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])

                    if self.current_start_range is not None:
                        self.current_start_range.extend(ranges)

                    charset_name = self.new_charset_name()
                    self.lexer_header += '{charset_name} = list(chain({charset}))\n'.format(charset_name=charset_name, charset=', '.join(['range({start}, {end})'.format(start=chr_range[0], end=chr_range[1]) for chr_range in ranges]))
                    return self.line('current += self.create_node(UnlexerRule(src=self.char_from_list({charset_name})))'.format(charset_name=charset_name))

            return ''.join([self.generate_single(child, parent_id, new_alt_ids) for child in node.children])

        if isinstance(node, self.parser.TerminalContext):
            if node.TOKEN_REF():
                self.graph.add_edge(frm=parent_id, to=str(node.TOKEN_REF()))
                return self.line('current += self.lexer.{rule_name}(max_depth=max_depth - 1)'.format(rule_name=node.TOKEN_REF()))

            if node.STRING_LITERAL():
                src = str(node.STRING_LITERAL())[1:-1]
                if self.current_start_range is not None:
                    self.current_start_range.append((ord(src[0]), ord(src[0]) + 1))
                return self.line('current += self.create_node(UnlexerRule(src=\'{src}\'))'.format(src=src))

        if isinstance(node, ParserRuleContext) and node.getChildCount():
            return ''.join([self.generate_single(child, parent_id, new_alt_ids) for child in node.children])

        return ''

    def generate_depths(self, lexer_ids, parser_ids):
        min_depths = self.graph.calc_min_depths()

        with self.indent():
            self.lexer_body += self.line('min_depths = {')
            with self.indent():
                self.lexer_body += ''.join([self.line('{id!r}: {depth!r},'.format(id=id, depth=min_depths[id])) for id in sorted(lexer_ids)])
            self.lexer_body += self.line('}\n')

            self.parser_body += self.line('min_depths = {')
            with self.indent():
                self.parser_body += ''.join([self.line('{id!r}: {depth!r},'.format(id=id, depth=min_depths[id])) for id in sorted(parser_ids)])
            self.parser_body += self.line('}\n')


class FuzzerFactory(object):
    """
    Class that generates fuzzers from grammars.
    """
    def __init__(self, work_dir=None, antlr=default_antlr_path):
        """
        :param work_dir: Directory to generate fuzzers into.
        :param antlr: Path to the ANTLR jar.
        """
        self.work_dir = work_dir or getcwd()

        antlr_dir = join(self.work_dir, 'antlr')
        makedirs(antlr_dir, exist_ok=True)
        # Add the path of the built grammars to the Python path to be available at parsing.
        if antlr_dir not in sys.path:
            sys.path.append(antlr_dir)

        self.lexer, self.parser, self.listener = build_grammars(antlr_dir, antlr=antlr)

    def generate_fuzzer(self, grammars, *, actions=True, pep8=False):
        """
        Generates fuzzers from grammars.

        :param grammars: List of grammar files to generate from.
        :param actions: Boolean to enable or disable grammar actions.
        :param pep8: Boolean to enable pep8 to beautify the generated fuzzer source.
        """
        lexer_root, parser_root = None, None

        for grammar in grammars:
            root = self._parse(grammar)
            # Lexer and/or combined grammars are processed first to evaluate TOKEN_REF-s.
            if root.grammarType().LEXER() or not root.grammarType().PARSER():
                lexer_root = root
            else:
                parser_root = root

        fuzzer_generator = FuzzerGenerator(self.parser, actions)
        for name, src in fuzzer_generator.generate(lexer_root, parser_root):
            with open(join(self.work_dir, name + '.py'), 'w') as f:
                if pep8:
                    src = autopep8.fix_code(src)
                f.write(src)

    def _collect_imports(self, root, base_dir):
        imports = set()
        for prequel in root.prequelConstruct():
            if prequel.delegateGrammars():
                for delegate_grammar in prequel.delegateGrammars().delegateGrammar():
                    ident = delegate_grammar.identifier(0)
                    imports.add(join(base_dir, str(ident.RULE_REF() or ident.TOKEN_REF()) + '.g4'))
        return imports

    def _parse(self, grammar):
        work_list = {grammar}
        root = None

        while work_list:
            grammar = work_list.pop()

            target_parser = self.parser(CommonTokenStream(self.lexer(FileStream(grammar, encoding='utf-8'))))
            current_root = target_parser.grammarSpec()
            # assert target_parser._syntaxErrors > 0, 'Parse error in ANTLR grammar.'

            # Save the 'outermost' grammar.
            if not root:
                root = current_root
            else:
                # Unite the rules of the imported grammar with the host grammar's rules.
                for rule in current_root.rules().ruleSpec():
                    root.rules().addChild(rule)

            work_list |= self._collect_imports(current_root, dirname(grammar))

        return root


def execute():
    parser = ArgumentParser(description='Grammarinator: Processor')
    parser.add_argument('grammars', nargs='+', metavar='FILE',
                        help='ANTLR grammar files describing the expected format to generate.')
    parser.add_argument('--antlr', metavar='FILE', default=default_antlr_path,
                        help='path of the ANTLR jar file (default: %(default)s).')
    parser.add_argument('--no-actions', dest='actions', default=True, action='store_false',
                        help='do not process inline actions (default: %(default)s).')
    parser.add_argument('--pep8', default=False, action='store_true',
                        help='enable autopep8 to format the generated fuzzer.')
    parser.add_argument('--log-level', metavar='LEVEL', default=logging.INFO,
                        help='verbosity level of diagnostic messages (default: %(default)s).')
    parser.add_argument('-o', '--out', metavar='DIR', default=getcwd(),
                        help='temporary working directory (default: .).')
    parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))
    args = parser.parse_args()

    logger.setLevel(args.log_level)

    for grammar in args.grammars:
        if not exists(grammar):
            parser.error('{grammar} does not exist.'.format(grammar=grammar))

    if args.antlr == default_antlr_path:
        antlerinator.install(lazy=True)

    FuzzerFactory(args.out, args.antlr).generate_fuzzer(args.grammars, actions=args.actions, pep8=args.pep8)


if __name__ == '__main__':
    execute()
