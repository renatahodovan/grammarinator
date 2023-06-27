# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
# Copyright (c) 2020 Sebastian Kimberk.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import re

from collections import defaultdict, OrderedDict
from itertools import chain
from math import inf
from os import getcwd
from os.path import dirname, exists, join
from pkgutil import get_data
from shutil import copy
from sys import maxunicode

import autopep8

from antlr4 import CommonTokenStream, FileStream, ParserRuleContext
from jinja2 import Environment

from ..pkgdata import __version__
from .g4 import ANTLRv4Lexer, ANTLRv4Parser

logger = logging.getLogger(__name__)


class Edge(object):

    def __init__(self, dst, args=None):
        self.dst = dst
        self.args = args


class Node(object):

    _cnt = 0

    def __init__(self, id=None):
        if id is None:
            id = Node._cnt
            Node._cnt += 1
        self.id = id
        self.out_edges = []

    @property
    def out_neighbours(self):
        return [edge.dst for edge in self.out_edges]

    def print_tree(self):
        def _walk(node):
            nonlocal indent
            print(f'{"  " * indent}{str(node)}{"" if node not in visited else " (...recursion)"}')
            if node in visited:
                return

            visited.add(node)
            indent += 1
            for child in node.out_neighbours:
                _walk(child)
            indent -= 1

        visited = set()
        indent = 0
        _walk(self)

    def __str__(self):
        return f'cls: {self.__class__.__name__}'


class RuleNode(Node):

    def __init__(self, name, label, type):
        super().__init__(name if label is None else '_'.join((name, label)))
        self.name = name
        self.type = type
        self.min_depth = None

        self.labels = {}
        self.args = {}
        self.locals = {}
        self.returns = {}

    @property
    def has_var(self):
        return self.labels or self.attributes

    @property
    def attributes(self):
        return dict(self.args, **self.locals, **self.returns)

    def __str__(self):
        return f'{super().__str__()}; name: {self.name}; var: {self.has_var}'


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

    def __init__(self, src):
        super().__init__()
        self.src = src

    def __str__(self):
        return f'{super().__str__()}; src: {self.src!r}'


class CharsetNode(Node):

    def __init__(self, rule_id, idx, charset):
        super().__init__()
        self.rule_id = rule_id  # Identifier of the container rule.
        self.idx = idx  # Index of the charset inside the current rule.
        self.charset = charset  # Global identifier of the charset.

    def __str__(self):
        return f'{super().__str__()}; idx: {self.idx}; charset: {self.charset}'


class LambdaNode(Node):

    def __init__(self):
        super().__init__()


class AlternationNode(Node):

    def __init__(self, rule_id, idx, conditions):
        super().__init__()
        self.rule_id = rule_id  # Identifier of the container rule.
        self.idx = idx  # Index of the alternation in the container rule.
        self.conditions = conditions
        self.min_depths = None

    def simple_alternatives(self):
        # Check if an alternation contains simple alternatives only (simple
        # literals or rule references), and return a 2-tuple. If the alternation
        # contains any non-simple alternatives, return None, None. If the
        # alternation contains simple literals only, the first element of the
        # tuple is a list of the literal values, while the second element is None.
        # If the alternation contains rule references only, the first element is
        # None, while the second element is a list of rule ids. If the alternation
        # contains both simple literals and rule references, then both elements of
        # the tuple are lists, which are of identical length, and exactly one of
        # them contains a non-None value at every index position.
        if not self.out_neighbours or any(len(alt.out_neighbours) != 1 or not isinstance(alt.out_neighbours[0], (LiteralNode, RuleNode)) for alt in self.out_neighbours):
            return None, None

        simple_lits = [alt.out_neighbours[0].src if isinstance(alt.out_neighbours[0], LiteralNode) else None for alt in self.out_neighbours]
        if all(lit is None for lit in simple_lits):
            simple_lits = None

        simple_rules = [alt.out_neighbours[0].id if isinstance(alt.out_neighbours[0], RuleNode) else None for alt in self.out_neighbours]
        if all(rule is None for rule in simple_rules):
            simple_rules = None

        return simple_lits, simple_rules

    def __str__(self):
        return f'{super().__str__()}; idx: {self.idx}; cond: {", ".join(self.conditions)}'


class AlternativeNode(Node):

    def __init__(self, rule_id, alt_idx, idx):
        super().__init__()
        self.rule_id = rule_id  # Identifier of the container rule.
        self.alt_idx = alt_idx  # Index of the container alternation inside the container rule.
        self.idx = idx  # Index of the alternative in the container alternation.

    def __str__(self):
        return f'{super().__str__()}; idx: {self.idx}'


class QuantifierNode(Node):

    def __init__(self, rule_id, idx, min, max):
        super().__init__()
        self.rule_id = rule_id  # Identifier of the container rule.
        self.idx = idx  # Index of the quantifier in the container rule.
        self.min = min
        self.max = max
        self.min_depth = None

    def __str__(self):
        return f'{super().__str__()}; idx: {self.idx}; min: {self.min}; max: {self.max}'


class ActionNode(Node):

    def __init__(self, src):
        super().__init__()
        self.src = src

    def __str__(self):
        return f'{super().__str__()}; src: {self.src}'


class VariableNode(Node):

    def __init__(self, name, is_list):
        super().__init__()
        self.name = name
        self.is_list = is_list

    def __str__(self):
        return f'{super().__str__()}; name: {self.name}; list: {self.is_list}'


def printable_ranges(lower_bound, upper_bound):
    ranges = []
    range_start = None
    for c in range(lower_bound, upper_bound):
        if chr(c).isprintable():
            if range_start is None:
                range_start = c
        else:
            if range_start is not None:
                ranges.append((range_start, c))
                range_start = None

    if range_start is not None:
        ranges.append((range_start, upper_bound))
    return ranges


def multirange_diff(r1_list, r2_list):
    def range_diff(r1, r2):
        s1, e1 = r1
        s2, e2 = r2
        endpoints = sorted((s1, s2, e1, e2))
        result = []
        if endpoints[0] == s1:
            result.append((endpoints[0], endpoints[1]))
        if endpoints[3] == e1:
            result.append((endpoints[2], endpoints[3]))
        return result

    for r2 in r2_list:
        r1_list = list(chain.from_iterable(range_diff(r1, r2) for r1 in r1_list))
    return r1_list


class Charset(object):

    dot = {
        'any_ascii_letter': [(ord('A'), ord('Z') + 1), (ord('a'), ord('z') + 1)],
        'any_ascii_char': printable_ranges(0x00, 0x80),
        'any_unicode_char': printable_ranges(0, maxunicode + 1),
    }

    _cnt = 0

    def __init__(self, ranges):
        self.id = Charset._cnt
        Charset._cnt += 1
        self.ranges = ranges


class GrammarGraph(object):

    def __init__(self):
        self.name = None
        self.vertices = OrderedDict()
        self.options = {}
        self.charsets = []
        self.header = ''
        self.members = ''
        self.default_rule = None

    @property
    def superclass(self):
        return self.options.get('superClass', 'Generator')

    @property
    def dot(self):
        return self.options.get('dot', 'any_ascii_char')

    @property
    def rules(self):
        return (vertex for vertex in self.vertices.values() if isinstance(vertex, RuleNode))

    @property
    def imag_rules(self):
        return (vertex for vertex in self.vertices.values() if isinstance(vertex, ImagRuleNode))

    def print_tree(self, root=None):
        if not root and not self.default_rule:
            raise ValueError('Either `root` must be defined or `print` should be called after `default_rule` is set.')
        (root or self.vertices[self.default_rule]).print_tree()

    def add_node(self, node):
        self.vertices[node.id] = node
        return node.id

    def add_edge(self, frm, to, args=None):
        assert frm in self.vertices, f'{frm} not in vertices.'
        assert to in self.vertices, f'{to} not in vertices.'
        self.vertices[frm].out_edges.append(Edge(dst=self.vertices[to], args=args))

    def calc_min_depths(self):
        min_depths = defaultdict(lambda: inf)
        changed = True

        while changed:
            changed = False
            for ident, node in self.vertices.items():
                selector = min if isinstance(node, AlternationNode) else max
                min_depth = selector((min_depths[out_node.id] + int(isinstance(out_node, RuleNode))
                                      for out_node in node.out_neighbours if not isinstance(out_node, QuantifierNode) or out_node.min > 0), default=0)

                if min_depth < min_depths[ident]:
                    min_depths[ident] = min_depth
                    changed = True

        for ident, node in self.vertices.items():
            if isinstance(node, RuleNode):
                node.min_depth = min_depths[ident]
            elif isinstance(node, QuantifierNode):
                node.min_depth = 0 if node.min > 0 else min_depths[ident]
            elif isinstance(node, AlternationNode):
                # Lift the minimal depths of the alternatives to the alternations, where the decision will happen.
                node.min_depths = [min_depths[alt.id] for alt in node.out_neighbours]


def escape_string(s):
    # To be kept in sync with Python's unicode_escape encoding at CPython's
    # Objects/unicodeobject.c:PyUnicode_AsUnicodeEscapeString, with the addition
    # of also escaping quotes.
    escapes = {
        '\t': '\\t',
        '\n': '\\n',
        '\r': '\\r',
        '\\': '\\\\',
        '\'': '\\\''
    }

    def _iter_escaped_chars(si):
        for ch in si:
            esc = escapes.get(ch)
            if esc is not None:
                yield esc

            else:
                cp = ord(ch)
                if 0x20 <= cp < 0x7f:
                    yield ch
                elif cp < 0x100:
                    yield f'\\x{cp:02x}'
                elif cp < 0x10000:
                    yield f'\\u{cp:04x}'
                else:
                    yield f'\\U{cp:08x}'

    return ''.join(c for c in _iter_escaped_chars(s))


class ProcessorTool(object):
    """
    Class to process ANTLRv4 grammar files, build an internal representation
    from them and create a generator class that is able to produce textual data
    according to the grammar files.
    """
    def __init__(self, lang, work_dir=None):
        """
        :param str lang: Language of the generated code (currently, only ``'py'`` is accepted as Python is the only supported language).
        :param str work_dir: Directory to generate fuzzers into (default: the current working directory).
        """
        self._lang = lang
        env = Environment(trim_blocks=True,
                          lstrip_blocks=True,
                          keep_trailing_newline=False)
        env.filters['substitute'] = lambda s, frm, to: re.sub(frm, to, str(s))
        env.filters['escape_string'] = escape_string
        self._template = env.from_string(get_data(__package__, 'resources/codegen/GeneratorTemplate.' + lang + '.jinja').decode('utf-8'))
        self._work_dir = work_dir or getcwd()

    def process(self, grammars, *, options=None, default_rule=None, encoding='utf-8', errors='strict', lib_dir=None, actions=True, pep8=False):
        """
        Perform the four main steps:

          1. Parse the grammar files.
          2. Build an internal representation of the grammar.
          3. Translate the internal representation into a generator source code in the target language.
          4. Save the source code into file.

        :param list[str] grammars: List of grammar files to produce generator from.
        :param dict options: Options dictionary to override/extend the options set in the grammar.
               Currenly, the following options are supported:

                 1. ``superClass``: Define the ancestor for the current grammar. The generator of this grammar will be inherited from ``superClass``. (default: :class:`grammarinator.runtime.Generator`)
                 2. ``dot``: Define how to handle the ``.`` wildcard in the grammar. Three keywords are accepted:

                     1. ``any_ascii_letter``: generate any ASCII letters
                     2. ``any_ascii_char``: generate any ASCII characters
                     3. ``any_unicode_char``: generate any Unicode characters

                    (default: ``any_ascii_char``)

        :param str default_rule: Name of the default rule to start generation from (default: first parser rule in the grammar).
        :param str encoding: Grammar file encoding.
        :param str errors: Encoding error handling scheme.
        :param str lib_dir: Alternative directory to look for grammar imports beside the current working directory.
        :param bool actions: Boolean to enable grammar actions. If they are disabled then the inline actions and semantic
               predicates of the input grammar (snippets in ``{...}`` and ``{...}?`` form) are disregarded (i.e., no code is
               generated from them).
        :param bool pep8: Boolean to enable pep8 to beautify the generated fuzzer source.
        """
        lexer_root, parser_root = None, None

        for grammar in grammars:
            if grammar.endswith('.g4'):
                root = self._parse_grammar(grammar, encoding, errors, lib_dir)
                # Lexer and/or combined grammars are processed first to evaluate TOKEN_REF-s.
                if root.grammarDecl().grammarType().LEXER() or not root.grammarDecl().grammarType().PARSER():
                    lexer_root = root
                else:
                    parser_root = root
            else:
                copy(grammar, self._work_dir)

        graph = self._build_graph(actions, lexer_root, parser_root, options, default_rule)
        self._analyze_graph(graph)

        src = self._template.render(graph=graph, version=__version__).lstrip()
        with open(join(self._work_dir, graph.name + '.' + self._lang), 'w') as f:
            if pep8:
                src = autopep8.fix_code(src)
            f.write(src)

    def _parse_grammar(self, grammar, encoding, errors, lib_dir):
        work_list = {grammar}
        root = None

        while work_list:
            grammar = work_list.pop()

            antlr_parser = ANTLRv4Parser(CommonTokenStream(ANTLRv4Lexer(FileStream(grammar, encoding=encoding, errors=errors))))
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

    @staticmethod
    def _build_graph(actions, lexer_root, parser_root, options, default_rule):

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
            start_cp, start_offset = process_lexer_char(start, 0)
            end_cp, end_offset = process_lexer_char(end, 0)

            if start_offset < len(start) or end_offset < len(end):
                raise ValueError(f'Only single characters are allowed in character ranges ({start!r}..{end!r})')

            return start_cp, end_cp + 1

        def process_lexer_char(s, offset):
            # To be kept in sync with org.antlr.v4.misc.EscapeSequenceParsing.parseEscape

            # Original Java code has to handle unicode codepoints which consist of more than one character,
            # however in Python 3.3+, we don't have to worry about this: https://stackoverflow.com/a/42262842

            if s[offset] != '\\':
                return ord(s[offset]), offset + 1

            if offset + 2 > len(s):
                raise ValueError('Escape must have at least two characters')

            escaped = s[offset + 1]
            offset += 2  # Move past backslash and escaped character

            if escaped == 'u':
                if s[offset] == '{':
                    # \u{...}
                    hex_start_offset = offset + 1
                    hex_end_offset = s.find('}', hex_start_offset)
                    if hex_end_offset == -1:
                        raise ValueError('Missing closing bracket for unicode escape')
                    if hex_start_offset == hex_end_offset:
                        raise ValueError('Missing codepoint for unicode escape')

                    offset = hex_end_offset + 1  # Skip over last bracket
                else:
                    # \uXXXX
                    hex_start_offset = offset
                    hex_end_offset = hex_start_offset + 4
                    if hex_end_offset > len(s):
                        raise ValueError('Non-bracketed unicode escape must be of form \\uXXXX')

                    offset = hex_end_offset

                try:
                    codepoint = int(s[hex_start_offset:hex_end_offset], 16)
                except ValueError as exc:
                    raise ValueError('Invalid hex value') from exc

                if codepoint < 0 or codepoint > maxunicode:
                    raise ValueError('Invalid unicode codepoint')

                return codepoint, offset

            if escaped in ('p', 'P'):
                raise ValueError('Unicode properties (\\p{...}) are not supported')

            # To be kept in sync with org.antlr.v4.misc.CharSupport.ANTLRLiteralEscapedCharValue
            escaped_values = {
                'n': '\n',
                'r': '\r',
                'b': '\b',
                't': '\t',
                'f': '\f',
                '\\': '\\',
                # Additional escape sequences defined by org.antlr.v4.misc.EscapeSequenceParsing.parseEscape
                '-': '-',
                ']': ']',
                '\'': '\''
            }

            if escaped in escaped_values:
                return ord(escaped_values[escaped]), offset

            raise ValueError('Invalid escaped value')

        def lexer_charset_interval(s):
            # To be kept in sync with org.antlr.v4.automata.LexerATNFactory.getSetFromCharSetLiteral
            assert len(s) > 0, 'Charset cannot be empty'

            ranges = []

            offset = 0
            while offset < len(s):
                in_range = s[offset] == '-' and offset != 0 and offset != len(s) - 1
                if in_range:
                    offset += 1

                codepoint, offset = process_lexer_char(s, offset)

                if in_range:
                    ranges[-1] = (ranges[-1][0], codepoint + 1)
                else:
                    ranges.append((codepoint, codepoint + 1))

            return ranges

        def chars_from_set(node):
            if node.characterRange():
                return [character_range_interval(node)]

            if node.LEXER_CHAR_SET():
                return lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])

            if node.STRING_LITERAL():
                char = str(node.STRING_LITERAL())[1:-1]
                char_cp, char_offset = process_lexer_char(char, 0)
                if char_offset < len(char):
                    raise ValueError(f'Zero or multi-character literals are not allowed in lexer sets: {char!r}')
                return [(char_cp, char_cp + 1)]

            if node.TOKEN_REF():
                src = str(node.TOKEN_REF())
                assert graph.vertices[src].start_ranges is not None, f'{src} has no character start ranges.'
                return graph.vertices[src].start_ranges

            return []

        def unescape_string(s):
            def _iter_unescaped_chars(s):
                offset = 0
                while offset < len(s):
                    codepoint, offset = process_lexer_char(s, offset)
                    yield chr(codepoint)

            return ''.join(c for c in _iter_unescaped_chars(s))

        def argActionBlock(node):
            args = {}
            if node and node.argActionBlock():
                for arg in ''.join(str(chr_arg) for chr_arg in node.argActionBlock().ARGUMENT_CONTENT()).split(','):
                    arg_name, arg_value = arg, None
                    if '=' in arg_name:
                        arg_name, arg_value = arg_name.split('=')
                    args[arg_name.strip()] = arg_value.strip() if arg_value else arg_value
            return args

        def build_rule(rule, node):
            lexer_rule = isinstance(rule, UnlexerRuleNode)
            alt_idx, quant_idx, chr_idx = 0, 0, 0  # pylint: disable=unused-variable

            def build_expr(node, parent_id):
                if isinstance(node, ANTLRv4Parser.ParserRuleSpecContext):
                    if actions:
                        rule.args = argActionBlock(node)
                        rule.locals = argActionBlock(node.localsSpec())
                        rule.returns = argActionBlock(node.ruleReturns())
                    build_expr(node.ruleBlock(), parent_id)

                elif isinstance(node, (ANTLRv4Parser.RuleAltListContext, ANTLRv4Parser.AltListContext, ANTLRv4Parser.LexerAltListContext)):
                    children = [child for child in node.children if isinstance(child, ParserRuleContext)]
                    if len(children) == 1:
                        build_expr(children[0], parent_id)
                        return

                    nonlocal alt_idx
                    alt_id = graph.add_node(AlternationNode(idx=alt_idx, conditions=[find_conditions(child) for child in children], rule_id=rule.name))
                    alt_idx += 1
                    graph.add_edge(frm=parent_id, to=alt_id)

                    for i, child in enumerate(children):
                        alternative_id = graph.add_node(AlternativeNode(rule_id=rule.name, alt_idx=graph.vertices[alt_id].idx, idx=i))
                        graph.add_edge(frm=alt_id, to=alternative_id)
                        build_expr(child, alternative_id)

                elif isinstance(node, ANTLRv4Parser.LabeledAltContext):
                    if not node.identifier():
                        build_expr(node.alternative(), parent_id)
                        return

                    rule_node = UnparserRuleNode(name=rule.name, label=str(node.identifier().TOKEN_REF() or node.identifier().RULE_REF()))
                    graph.add_edge(frm=parent_id, to=graph.add_node(rule_node))
                    build_rule(rule_node, node.alternative())

                elif isinstance(node, (ANTLRv4Parser.AlternativeContext, ANTLRv4Parser.LexerAltContext)):
                    children = node.element() if isinstance(node, ANTLRv4Parser.AlternativeContext) else node.lexerElements().lexerElement()
                    for child in children:
                        build_expr(child, parent_id)

                    if not graph.vertices[parent_id].out_neighbours:
                        graph.add_edge(frm=parent_id, to=lambda_id)

                elif isinstance(node, (ANTLRv4Parser.ElementContext, ANTLRv4Parser.LexerElementContext)):
                    if node.actionBlock():
                        # Conditions are handled at alternative processing.
                        if not actions or node.QUESTION():
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
                    quant_id = graph.add_node(QuantifierNode(rule_id=rule.name, idx=quant_idx, **quant_ranges[suffix]))
                    quant_idx += 1
                    graph.add_edge(frm=parent_id, to=quant_id)
                    build_expr(node.children[0], quant_id)

                elif isinstance(node, ANTLRv4Parser.LabeledElementContext):
                    build_expr(node.atom() or node.block(), parent_id)
                    ident = node.identifier()
                    name = str(ident.RULE_REF() or ident.TOKEN_REF())
                    is_list = node.PLUS_ASSIGN() is not None
                    graph.add_edge(frm=parent_id, to=graph.add_node(VariableNode(name=name, is_list=is_list)))
                    rule.labels[name] = is_list

                elif isinstance(node, ANTLRv4Parser.RulerefContext):
                    graph.add_edge(frm=parent_id, to=str(node.RULE_REF()), args=argActionBlock(node) if actions else None)

                elif isinstance(node, (ANTLRv4Parser.LexerAtomContext, ANTLRv4Parser.AtomContext)):
                    nonlocal chr_idx

                    if node.DOT():
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.name, idx=chr_idx, charset=dot_charset.id)))
                        chr_idx += 1

                    elif node.notSet():
                        if node.notSet().setElement():
                            not_ranges = chars_from_set(node.notSet().setElement())
                        else:
                            not_ranges = []
                            for set_element in node.notSet().blockSet().setElement():
                                not_ranges.extend(chars_from_set(set_element))

                        charset = Charset(multirange_diff(dot_charset.ranges, sorted(not_ranges, key=lambda x: x[0])))
                        graph.charsets.append(charset)
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.name, idx=chr_idx, charset=charset.id)))
                        chr_idx += 1

                    elif isinstance(node, ANTLRv4Parser.LexerAtomContext) and node.characterRange():
                        start, end = character_range_interval(node)
                        if lexer_rule:
                            rule.start_ranges.append((start, end))

                        charset = Charset([(start, end)])
                        graph.charsets.append(charset)
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.name, idx=chr_idx, charset=charset.id)))
                        chr_idx += 1

                    elif isinstance(node, ANTLRv4Parser.LexerAtomContext) and node.LEXER_CHAR_SET():
                        ranges = lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])
                        if lexer_rule:
                            rule.start_ranges.extend(ranges)

                        charset = Charset(sorted(ranges, key=lambda x: x[0]))
                        graph.charsets.append(charset)
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.name, idx=chr_idx, charset=charset.id)))
                        chr_idx += 1

                    for child in node.children:
                        build_expr(child, parent_id)

                elif isinstance(node, ANTLRv4Parser.TerminalContext):
                    if node.TOKEN_REF():
                        graph.add_edge(frm=parent_id, to=str(node.TOKEN_REF()))

                    elif node.STRING_LITERAL():
                        src = unescape_string(str(node.STRING_LITERAL())[1:-1])

                        if lexer_rule:
                            rule.start_ranges.append((ord(src[0]), ord(src[0]) + 1))

                        graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(src=src)))

                elif isinstance(node, ParserRuleContext) and node.getChildCount():
                    for child in node.children:
                        build_expr(child, parent_id)

            if lexer_rule:
                rule.start_ranges = []

            build_expr(node, rule.id)

        def build_prequel(node):
            assert isinstance(node, ANTLRv4Parser.GrammarSpecContext)

            if not graph.name:
                graph.name = re.sub(r'^(.+?)(Lexer|Parser)?$', r'\1Generator', str(node.grammarDecl().identifier().TOKEN_REF() or node.grammarDecl().identifier().RULE_REF()))

            for prequelConstruct in node.prequelConstruct() if node.prequelConstruct() else ():
                for option in prequelConstruct.optionsSpec().option() if prequelConstruct.optionsSpec() else ():
                    ident = option.identifier()
                    ident = str(ident.RULE_REF() or ident.TOKEN_REF())
                    graph.options[ident] = option.optionValue().getText()

                for identifier in prequelConstruct.tokensSpec().idList().identifier() if prequelConstruct.tokensSpec() and prequelConstruct.tokensSpec().idList() else ():
                    assert identifier.TOKEN_REF() is not None, 'Token names must start with uppercase letter.'
                    graph.add_node(ImagRuleNode(id=str(identifier.TOKEN_REF())))

                if prequelConstruct.action_() and actions:
                    action = prequelConstruct.action_()
                    action_ident = action.identifier()
                    action_type = str(action_ident.RULE_REF() or action_ident.TOKEN_REF())
                    raw_action_src = ''.join(str(child) for child in action.actionBlock().ACTION_CONTENT())

                    # We simply append both members and header code chunks to the generated source.
                    # It's the user's responsibility to define them in order.
                    if action_type == 'members':
                        graph.members += raw_action_src
                    elif action_type == 'header':
                        graph.header += raw_action_src

        def build_rules(node):
            generator_rules, duplicate_rules = [], []
            for rule in node.rules().ruleSpec():
                if rule.parserRuleSpec():
                    rule_spec = rule.parserRuleSpec()
                    rule_node = UnparserRuleNode(name=str(rule_spec.RULE_REF()))
                    antlr_node = rule_spec
                elif rule.lexerRuleSpec():
                    rule_spec = rule.lexerRuleSpec()
                    rule_node = UnlexerRuleNode(name=str(rule_spec.TOKEN_REF()))
                    antlr_node = rule_spec.lexerRuleBlock()
                else:
                    assert False, 'Should not get here.'

                if rule_node.id not in graph.vertices:
                    graph.add_node(rule_node)
                    generator_rules.append((rule_node, antlr_node))
                else:
                    duplicate_rules.append(rule_node.id)

            for mode_spec in node.modeSpec():
                for rule_spec in mode_spec.lexerRuleSpec():
                    rule_node = UnlexerRuleNode(name=str(rule_spec.TOKEN_REF()))
                    if rule_node.id not in graph.vertices:
                        graph.add_node(rule_node)
                        generator_rules.append((rule_node, rule_spec.lexerRuleBlock()))
                    else:
                        duplicate_rules.append(rule_node.id)

            if duplicate_rules:
                raise ValueError(f'Rule redefinition(s): {", ".join(duplicate_rules)}')

            for rule_args in generator_rules:
                build_rule(*rule_args)

            if default_rule:
                graph.default_rule = default_rule
            elif node.grammarDecl().grammarType().PARSER() or not (node.grammarDecl().grammarType().LEXER() or node.grammarDecl().grammarType().PARSER()):
                graph.default_rule = generator_rules[0][0].name

        graph = GrammarGraph()
        lambda_id = graph.add_node(LambdaNode())
        graph.add_node(UnlexerRuleNode(name='EOF'))

        for root in [lexer_root, parser_root]:
            if root:
                build_prequel(root)
        graph.options.update(options or {})

        dot_charset = Charset(Charset.dot[graph.dot])
        graph.charsets.append(dot_charset)

        for root in [lexer_root, parser_root]:
            if root:
                build_rules(root)

        graph.calc_min_depths()
        return graph

    # Calculates the distance of every rule node from the start node. As a result, it can
    # point out to rules, that are not available from there, furthermore it can give a hint
    # about the farthest node/rule to help to determine a max_depth that has the chance to
    # reach every rule. Also checks for infinite derivations.
    @staticmethod
    def _analyze_graph(graph, root=None):
        root = root or graph.default_rule
        min_distances = defaultdict(lambda: inf)
        min_distances[root] = 0

        work_list = [root]
        while work_list:
            v = work_list.pop(0)
            for out_v in graph.vertices[v].out_neighbours:
                d = min_distances[v] + int(isinstance(out_v, RuleNode))
                if d < min_distances[out_v.id]:
                    min_distances[out_v.id] = d
                    work_list.append(out_v.id)

        farthest_ident, max_distance = max(((v_id, d) for v_id, d in min_distances.items() if (isinstance(graph.vertices[v_id], RuleNode) and d != inf)), key=lambda item: item[1])
        unreachable_rules = [v_id for v_id, v in graph.vertices.items() if isinstance(v, RuleNode) and min_distances[v_id] == inf]

        logger.info('\tThe farthest rule from %r is %r (%d steps).', root, farthest_ident, max_distance)
        if unreachable_rules:
            logger.warning('\t%d rule(s) unreachable from %r: %s', len(unreachable_rules), root, ', '.join(map(repr, unreachable_rules)))

        inf_alts = []
        inf_rules = []
        for ident, node in graph.vertices.items():
            if isinstance(node, AlternationNode):
                for alternative_idx, alternative_node in enumerate(node.out_neighbours):
                    if node.min_depths[alternative_idx] == inf:
                        # Generate human-readable description for an alternative in the graph. The output is a
                        # (rule node, alternation node, alternative node) string, where `rule` defines the container
                        # rule and the (alternation node, alternative node) sequence defines a derivation reaching the alternative.
                        inf_alts.append(', '.join(map(str, [graph.vertices[alternative_node.rule_id], node, alternative_node])))
            elif isinstance(node, RuleNode):
                if node.min_depth == inf:
                    inf_rules.append(ident)
        if inf_alts:
            logger.warning('\t%d alternative(s) with infinite derivation (rule node, alternation node, alternative node):\n\t%s', len(inf_alts), ',\n\t'.join(inf_alts))
        if inf_rules:
            logger.warning('\t%d rule(s) with infinite derivation (possible cycles): %s', len(inf_rules), ', '.join(map(repr, inf_rules)))
