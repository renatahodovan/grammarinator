# Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
# Copyright (c) 2020 Sebastian Kimberk.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from __future__ import annotations

import logging

from collections import Counter, defaultdict, OrderedDict
from itertools import chain
from math import inf
from os import getcwd
from os.path import dirname, exists, join
from pkgutil import get_data
from shutil import copy
from sys import maxunicode
from typing import ClassVar, DefaultDict, Generator, Optional, Union

import autopep8
import regex as re

from antlr4 import CommonTokenStream, FileStream, ParserRuleContext, RuleContext
from jinja2 import Environment

from ..pkgdata import __version__
from .g4 import ANTLRv4Lexer, ANTLRv4Parser

logger = logging.getLogger(__name__)


EdgeArgType = list[tuple[Optional[str], Optional[str], Optional[str]]]
RuleIdType = Union[str, tuple[str], tuple[str, str], tuple[str, str, int]]
NodeIdKeyType = Union[RuleIdType, tuple[int], tuple[int, str, int]]
NodeIdType = Union[NodeIdKeyType, tuple[NodeIdKeyType, str, int], tuple[NodeIdKeyType, str, int, int]]


class Edge:

    def __init__(self, dst: Node, args: Optional[EdgeArgType] = None) -> None:
        self.dst = dst
        self.args = args
        self.reserve: int = 0


class Node:

    _cnt: ClassVar[int] = 0

    def __init__(self, id: Optional[NodeIdType] = None) -> None:
        if id is None:
            id = (Node._cnt, )
            Node._cnt += 1
        self.id = id if isinstance(id, tuple) else (id, )
        self.out_edges: list[Edge] = []

    @property
    def out_neighbours(self) -> list[Node]:
        return [edge.dst for edge in self.out_edges]

    def print_tree(self) -> None:
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

        visited: set[Node] = set()
        indent = 0
        _walk(self)

    def __str__(self) -> str:
        return f'cls: {self.__class__.__name__}'


class NodeSize:

    def __init__(self, depth: Union[int, float], tokens: Union[int, float]) -> None:
        self.depth = depth
        self.tokens = tokens

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NodeSize) and self.depth == other.depth and self.tokens == other.tokens

    def __repr__(self) -> str:
        return f'NodeSize({self.depth}, {self.tokens})'


class RuleNode(Node):

    def __init__(self, name: RuleIdType, type: str, trampoline: bool = False) -> None:
        name = name if isinstance(name, tuple) else (name,)
        super().__init__(name)
        # Keep rule and label name, but exclude label index if exists.
        self.name = '_'.join(part for part in name[:2])
        self.type = type
        self.trampoline = trampoline
        self.min_size = NodeSize(depth=inf, tokens=inf)

        self.labels: dict[str, bool] = {}
        self.args: list[EdgeArgType] = []
        self.locals: list[EdgeArgType] = []
        self.returns: list[EdgeArgType] = []
        self.init: str = ''
        self.after: str = ''

    def __str__(self) -> str:
        return f'{super().__str__()}; name: {self.id}'


class UnlexerRuleNode(RuleNode):

    _lit_cnt: ClassVar[int] = 0

    def __init__(self, name: Optional[str] = None) -> None:
        if not name:
            name = f'T__{UnlexerRuleNode._lit_cnt}'
            UnlexerRuleNode._lit_cnt += 1
        super().__init__(name, 'UnlexerRule')
        self.start_ranges: Optional[list[tuple[int, int]]] = None


class UnparserRuleNode(RuleNode):

    def __init__(self, name: RuleIdType, trampoline: bool = False) -> None:
        super().__init__(name, 'UnparserRule', trampoline)


class ImagRuleNode(Node):

    def __init__(self, id: str) -> None:
        super().__init__(id)


class LiteralNode(Node):

    def __init__(self, src: str) -> None:
        super().__init__()
        self.src = src

    def __str__(self) -> str:
        return f'{super().__str__()}; src: {self.src!r}'


class CharsetNode(Node):

    def __init__(self, rule_id: RuleIdType, idx: int, charset: str) -> None:
        super().__init__()
        self.rule_id = rule_id  # Identifier of the container rule.
        self.idx = idx  # Index of the charset inside the current rule.
        self.charset = charset  # Global identifier of the charset.

    def __str__(self) -> str:
        return f'{super().__str__()}; idx: {self.idx}; charset: {self.charset}'


class LambdaNode(Node):

    def __init__(self) -> None:
        super().__init__()


class AlternationNode(Node):

    def __init__(self, rule_id: RuleIdType, idx: int, conditions: int) -> None:
        super().__init__((rule_id, 'alt', idx))
        self.rule_id = rule_id  # Identifier of the container rule.
        self.idx = idx  # Index of the alternation in the container rule.
        self.conditions = conditions  # Index of the condition in the GrammarGraph's `alt_conds` list.
        self.min_sizes: int = -1  # Index of the alternation in the GrammarGraph's `alt_sizes` list.

    def simple_alternatives(self) -> tuple[Optional[list[Optional[str]]], Optional[list[Optional[NodeIdType]]]]:
        # Check if an alternation contains simple alternatives only (simple
        # literals or rule references without arguments), and return a 2-tuple. If the alternation
        # contains any non-simple alternatives, return None, None. If the
        # alternation contains simple literals only, the first element of the
        # tuple is a list of the literal values, while the second element is None.
        # If the alternation contains rule references only, the first element is
        # None, while the second element is a list of rule ids. If the alternation
        # contains both simple literals and rule references, then both elements of
        # the tuple are lists, which are of identical length, and exactly one of
        # them contains a non-None value at every index position.
        if (not self.out_neighbours
            or any(len(alt.out_neighbours) != 1
                   or not isinstance(alt.out_neighbours[0], (LiteralNode, RuleNode))
                   or (isinstance(alt.out_neighbours[0], RuleNode) and alt.out_edges[0].args)
                   for alt in self.out_neighbours)):
            return None, None

        lits_list: list[Optional[str]] = [
            alt.out_neighbours[0].src if isinstance(alt.out_neighbours[0], LiteralNode) else None
            for alt in self.out_neighbours
        ]
        rules_list: list[Optional[NodeIdType]] = [
            alt.out_neighbours[0].id if isinstance(alt.out_neighbours[0], RuleNode) else None
            for alt in self.out_neighbours
        ]

        simple_lits: Optional[list[Optional[str]]] = None if all(x is None for x in lits_list) else lits_list
        simple_rules: Optional[list[Optional[NodeIdType]]] = None if all(x is None for x in rules_list) else rules_list

        return simple_lits, simple_rules

    def __str__(self) -> str:
        return f'{super().__str__()}; idx: {self.idx}; conditions: {self.conditions}'


class AlternativeNode(Node):

    def __init__(self, rule_id: RuleIdType, alt_idx: int, idx: int) -> None:
        super().__init__((rule_id, 'alt', alt_idx, idx))
        self.rule_id = rule_id  # Identifier of the container rule.
        self.alt_idx = alt_idx  # Index of the container alternation inside the container rule.
        self.idx = idx  # Index of the alternative in the container alternation.

    @property
    def is_lambda_alternative(self) -> bool:
        return len(self.out_neighbours) == 1 and isinstance(self.out_neighbours[0], LambdaNode)

    def __str__(self) -> str:
        return f'{super().__str__()}; idx: {self.idx}'


class QuantifierNode(Node):

    def __init__(self, rule_id: RuleIdType, idx: int, start: int, stop: Union[int, float]) -> None:
        super().__init__((rule_id, 'quant', idx))
        self.rule_id = rule_id  # Identifier of the container rule.
        self.idx = idx  # Index of the quantifier in the container rule.
        self.start = start
        self.stop = stop
        self.min_size: int = -1

    def __str__(self) -> str:
        return f'{super().__str__()}; idx: {self.idx}; start: {self.start}; stop: {self.stop}'


class ActionNode(Node):

    def __init__(self, src: str) -> None:
        super().__init__()
        self.src = src

    def __str__(self) -> str:
        return f'{super().__str__()}; src: {self.src}'


class VariableNode(Node):

    def __init__(self, name: str, is_list: bool) -> None:
        super().__init__()
        self.name = name
        self.is_list = is_list

    def __str__(self) -> str:
        return f'{super().__str__()}; name: {self.name}; list: {self.is_list}'


def printable_ranges(lower_bound: int, upper_bound: int) -> list[tuple[int, int]]:
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


def multirange_diff(r1_list: list[tuple[int, int]], r2_list: list[tuple[int, int]]) -> list[tuple[int, int]]:
    def range_diff(r1, r2):
        s1, e1 = r1
        s2, e2 = r2
        endpoints = sorted((s1, s2, e1, e2))
        result = []
        if endpoints[0] == s1 and endpoints[0] != endpoints[1]:
            result.append((endpoints[0], endpoints[1]))
        if endpoints[3] == e1 and endpoints[2] != endpoints[3]:
            result.append((endpoints[2], endpoints[3]))
        return result

    for r2 in r2_list:
        r1_list = list(chain.from_iterable(range_diff(r1, r2) for r1 in r1_list))
    return r1_list


def append_unique(container: list, element: object) -> int:
    if element in container:
        return container.index(element)

    container.append(element)
    return len(container) - 1


dot_ranges = {
    'any_ascii_letter': [(ord('A'), ord('Z') + 1), (ord('a'), ord('z') + 1)],
    'any_ascii_char': printable_ranges(0x00, 0x80),
    'any_unicode_char': printable_ranges(0, maxunicode + 1),
}


class GrammarGraph:

    def __init__(self) -> None:
        self.name: str = ''
        self.vertices: OrderedDict = OrderedDict()
        self.options: dict[str, str] = {}
        self.charsets: list[list[tuple[int, int]]] = []
        self.alt_conds: list[AlternationNode] = []
        self.alt_sizes: list[list[NodeSize]] = []
        self.quant_sizes: list[NodeSize] = []
        self.immutables: Optional[list[NodeIdType]] = None
        self.header: str = ''
        self.members: str = ''
        self.default_rule: str = ''

    @property
    def superclass(self) -> str:
        return self.options.get('superClass', 'Generator')

    @property
    def dot(self) -> str:
        return self.options.get('dot', 'any_ascii_char')

    @property
    def rules(self) -> Generator[RuleNode, None, None]:
        return (vertex for vertex in self.vertices.values() if isinstance(vertex, RuleNode))

    @property
    def imag_rules(self) -> Generator[ImagRuleNode, None, None]:
        return (vertex for vertex in self.vertices.values() if isinstance(vertex, ImagRuleNode))

    def print_tree(self, root: Optional[Node] = None) -> None:
        if not root and not self.default_rule:
            raise ValueError('Either `root` must be defined or `print_tree` should be called after `default_rule` is set.')
        (root or self.vertices[(self.default_rule,)]).print_tree()

    def add_node(self, node: Node) -> NodeIdType:
        self.vertices[node.id] = node
        return node.id

    def add_edge(self, frm: NodeIdType, to: NodeIdType, args: Optional[EdgeArgType] = None) -> None:
        frm = frm if isinstance(frm, tuple) else (frm,)
        to = to if isinstance(to, tuple) else (to,)
        assert frm in self.vertices, f'{frm} not in vertices.'
        assert to in self.vertices, f'{to} not in vertices.'
        self.vertices[frm].out_edges.append(Edge(dst=self.vertices[to], args=args))

    def calc_min_sizes(self) -> None:
        min_sizes: DefaultDict[NodeIdType, NodeSize] = defaultdict(lambda: NodeSize(depth=inf, tokens=inf))

        # Calculcate the size metrics for all the subtrees.
        changed = True
        while changed:
            changed = False
            for ident, node in self.vertices.items():
                children_sizes = [min_sizes[out_node.id] for out_node in node.out_neighbours]

                if isinstance(node, UnlexerRuleNode):
                    min_depth = max((c.depth for c in children_sizes), default=0) + 1
                    min_tokens = sum(c.tokens for c in children_sizes) + 1
                elif isinstance(node, UnparserRuleNode):
                    min_depth = max((c.depth for c in children_sizes), default=0) + 1
                    min_tokens = sum(c.tokens for c in children_sizes)
                elif isinstance(node, AlternativeNode):
                    min_depth = max((c.depth for c in children_sizes), default=0)
                    min_tokens = sum(c.tokens for c in children_sizes)
                elif isinstance(node, AlternationNode):
                    min_depth = min((c.depth for c in children_sizes), default=0)
                    min_tokens = min((c.tokens for c in children_sizes), default=0)
                elif isinstance(node, QuantifierNode):
                    if node.start > 0:
                        min_depth = max((c.depth for c in children_sizes), default=0)
                        min_tokens = sum(c.tokens for c in children_sizes)
                    else:
                        min_depth, min_tokens = 0, 0
                else:
                    min_depth, min_tokens = 0, 0

                if min_depth < min_sizes[ident].depth:
                    min_sizes[ident].depth = min_depth
                    changed = True
                if min_tokens < min_sizes[ident].tokens:
                    min_sizes[ident].tokens = min_tokens
                    changed = True

        # Assign the calculated size metric values to the vertices participating in generator decisions.
        for ident, node in self.vertices.items():
            if isinstance(node, RuleNode):
                node.min_size = min_sizes[ident]
            elif isinstance(node, QuantifierNode):
                children_sizes = [min_sizes[out_node.id] for out_node in node.out_neighbours]
                min_size = NodeSize(depth=max((c.depth for c in children_sizes), default=0),
                                    tokens=sum(c.tokens for c in children_sizes))
                node.min_size = append_unique(self.quant_sizes, min_size)
            elif isinstance(node, AlternationNode):
                # Lift the minimal size of the alternatives to the alternations, where the decision will happen.
                # The sizes of the alternatives are 0 if the alternation is inside a token.
                node.min_sizes = append_unique(self.alt_sizes, [min_sizes[alt.id] for alt in node.out_neighbours])

        # In case of token size metric, calculate the minimum needed cost of finishing the generation (everything after the current node).
        for node in self.vertices.values():
            if isinstance(node, AlternationNode):
                continue
            reserve: Union[int, float] = 0
            for edge in reversed(node.out_edges):
                edge.reserve = reserve
                reserve += min_sizes[edge.dst.id].tokens

    def find_immutable_rules(self) -> None:
        changed = True
        immutables = set()
        while changed:
            changed = False
            for vertex in self.vertices.values():
                if isinstance(vertex, RuleNode) and all(isinstance(vout, LiteralNode) or vout.id in immutables for vout in vertex.out_neighbours):
                    if vertex.id not in immutables:
                        immutables.add(vertex.id)
                        changed = True
        self.immutables = sorted(immutables)


def escape_string(s: str) -> str:
    # To be kept in sync with Python's unicode_escape encoding at CPython's
    # Objects/unicodeobject.c:PyUnicode_AsUnicodeEscapeString, with the addition
    # of also escaping quotes.
    escapes = {
        '\t': '\\t',
        '\n': '\\n',
        '\r': '\\r',
        '\\': '\\\\',
        '\'': '\\\'',
        # C++ escape:
        '"': '\\"'
    }

    def _iter_escaped_chars(si: str) -> Generator[str]:
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


class ProcessorTool:
    """
    Tool to process ANTLRv4 grammar files, build an internal representation
    from them and create a generator class that is able to produce textual data
    according to the grammar files.
    """
    def __init__(self, lang: str, work_dir: Optional[str] = None) -> None:
        """
        :param lang: Language of the generated code (currently, ``'py'`` and ``'hpp'`` are accepted).
        :param work_dir: Directory to generate fuzzers into (default: the current working directory).
        """
        self._lang = lang
        env = Environment(trim_blocks=True,
                          lstrip_blocks=True,
                          keep_trailing_newline=False)
        env.filters['substitute'] = lambda s, frm, to: re.sub(frm, to, str(s))
        env.filters['escape_string'] = escape_string
        template_data = get_data(__package__, 'resources/codegen/GeneratorTemplate.' + lang + '.jinja')
        if template_data is None:
            raise ValueError(f'No template found for language: {lang!r}.')
        self._template: Environment = env.from_string(template_data.decode('utf-8'))  # Jinja2 template to generate the source code of the generator class.
        self._work_dir = work_dir or getcwd()

    def process(self, grammars: list[str], *, options: Optional[dict] = None, default_rule: Optional[str] = None, encoding: str = 'utf-8', errors: str = 'strict', lib_dir: Optional[str] = None, actions: bool = True, pep8: bool = False) -> None:
        """
        Perform the four main steps:

          1. Parse the grammar files.
          2. Build an internal representation of the grammar.
          3. Translate the internal representation into a generator source code in the target language.
          4. Save the source code into file.

        :param grammars: List of grammar files to produce generator from.
        :param options: Options dictionary to override/extend the options set in the grammar.
               Currenly, the following options are supported:

                 1. ``superClass``: Define the ancestor for the current grammar. The generator of this grammar will be inherited from ``superClass``. (default: :class:`grammarinator.runtime.Generator`)
                 2. ``dot``: Define how to handle the ``.`` wildcard in the grammar. Three keywords are accepted:

                     1. ``any_ascii_letter``: generate any ASCII letters
                     2. ``any_ascii_char``: generate any ASCII characters
                     3. ``any_unicode_char``: generate any Unicode characters

                    (default: ``any_ascii_char``)

        :param default_rule: Name of the default rule to start generation from (default: first parser rule in the grammar).
        :param encoding: Grammar file encoding.
        :param errors: Encoding error handling scheme.
        :param lib_dir: Alternative directory to look for grammar imports beside the current working directory.
        :param actions: Boolean to enable grammar actions. If they are disabled then the inline actions and semantic
               predicates of the input grammar (snippets in ``{...}`` and ``{...}?`` form) are disregarded (i.e., no code is
               generated from them).
        :param pep8: Boolean to enable pep8 to beautify the generated fuzzer source.
        """
        lexer_root, parser_root = ProcessorTool.parse_grammars(grammars, self._work_dir, encoding, errors, lib_dir)
        graph = ProcessorTool.build_graph(actions, lexer_root, parser_root, options, default_rule)
        ProcessorTool._analyze_graph(graph)

        src = self._template.render(graph=graph, version=__version__).lstrip()
        with open(join(self._work_dir, graph.name + '.' + self._lang), 'w') as f:
            if pep8:
                src = autopep8.fix_code(src)
            f.write(src)

    @staticmethod
    def parse_grammars(grammars: list[str], work_dir: str, encoding: str = 'utf-8', errors: str = 'strict', lib_dir: Optional[str] = None) -> tuple[Optional[ParserRuleContext], Optional[ParserRuleContext]]:
        lexer_root, parser_root = None, None

        for grammar in grammars:
            if grammar.endswith('.g4'):
                root = ProcessorTool._parse_grammar(grammar, encoding, errors, lib_dir)
                # Lexer and/or combined grammars are processed first to evaluate TOKEN_REF-s.
                if root.grammarDecl().grammarType().LEXER() or not root.grammarDecl().grammarType().PARSER():
                    lexer_root = root
                else:
                    parser_root = root
            else:
                copy(grammar, work_dir)

        return lexer_root, parser_root

    @staticmethod
    def _parse_grammar(grammar: str, encoding: str, errors: str, lib_dir: Optional[str] = None) -> ParserRuleContext:
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

            work_list |= ProcessorTool._collect_imports(current_root, dirname(grammar), lib_dir)

        return root

    @staticmethod
    def _collect_imports(root: ParserRuleContext, base_dir: str, lib_dir: Optional[str] = None) -> set[str]:
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
    def build_graph(actions: bool, lexer_root: Optional[RuleContext], parser_root: Optional[RuleContext], options: Optional[dict[str, str]], default_rule: Optional[str] = None) -> GrammarGraph:

        def find_conditions(node: Union[str, RuleContext]) -> str:
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

        def character_range_interval(node: RuleContext) -> tuple[int, int]:
            start = str(node.characterRange().STRING_LITERAL(0))[1:-1]
            end = str(node.characterRange().STRING_LITERAL(1))[1:-1]
            start_cp, start_offset = process_lexer_char(start, 0, 'character range')
            assert isinstance(start_cp, int), 'Start of character range cannot be a list of codepoints.'
            end_cp, end_offset = process_lexer_char(end, 0, 'character range')
            assert isinstance(end_cp, int), 'End of character range cannot be a list of codepoints.'

            if start_offset < len(start) or end_offset < len(end):
                raise ValueError(f'Only single characters are allowed in character ranges ({start!r}..{end!r})')

            return start_cp, end_cp + 1

        def process_lexer_char(s: str, offset: int, use_case: str) -> tuple[Union[int, list[tuple[int, int]]], int]:
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
                        raise ValueError(f'Missing closing bracket for unicode escape ({s})')
                    if hex_start_offset == hex_end_offset:
                        raise ValueError(f'Missing codepoint for unicode escape ({s})')

                    offset = hex_end_offset + 1  # Skip over last bracket
                else:
                    # \uXXXX
                    hex_start_offset = offset
                    hex_end_offset = hex_start_offset + 4
                    if hex_end_offset > len(s):
                        raise ValueError(f'Non-bracketed unicode escape must be of form \\uXXXX ({s})')

                    offset = hex_end_offset

                try:
                    codepoint = int(s[hex_start_offset:hex_end_offset], 16)
                except ValueError as exc:
                    raise ValueError(f'Invalid hex value ({s})') from exc

                if codepoint < 0 or codepoint > maxunicode:
                    raise ValueError(f'Invalid unicode codepoint ({s})')

                return codepoint, offset

            # \p{...}, \P{...}
            if escaped in ('p', 'P'):
                if use_case != 'lexer charset':
                    raise ValueError(f'Unicode properties are allowed in lexer charsets only (not in {use_case})')

                if s[offset] != '{':
                    raise ValueError(f'Unicode properties must use the format: `\\p{{...}}` ({s})')

                prop_start_offset = offset + 1
                prop_end_offset = s.find('}', prop_start_offset)
                if prop_end_offset == -1:
                    raise ValueError(f'Missing closing bracket for unicode property escape ({s})')
                if prop_start_offset == prop_end_offset:
                    raise ValueError(f'Missing property name for unicode property escape ({s})')

                offset = prop_end_offset + 1  # Skip over last bracket

                def _name_to_codepoints(uni_prop):
                    try:
                        pattern = re.compile(uni_prop)
                    except Exception as e:
                        raise ValueError(f'Unknown property: {uni_prop}') from e
                    return [cp for cp in range(maxunicode) if pattern.match(chr(cp))]

                # Collect continous ranges.
                def _codepoints_to_ranges(codepoints):
                    ranges = []
                    start, current = None, None
                    last_cp_id = len(codepoints) - 1
                    for i, code in enumerate(codepoints):
                        if not start:
                            start = current = code
                        elif code == current + 1:
                            current = code
                            if i == last_cp_id:
                                ranges.append((start, current + 1))
                        else:
                            ranges.append((start, current + 1))
                            start = current = code
                    return ranges

                prop_name = s[prop_start_offset:prop_end_offset]

                # The interpretation of 'Extended_Pictographic' differs between the `regex` lib and ANTLR.
                # ANTLR defines the ranges below manually, hence we do the same.
                if prop_name in ['Extended_Pictographic', 'EP']:
                    ranges = [(0x2388, 0x2389), (0x2605, 0x2606), (0x2607, 0x260d), (0x260f, 0x2610), (0x2612, 0x2613), (0x2616, 0x2617), (0x2619, 0x261c), (0x261e, 0x261f), (0x2621, 0x2622), (0x2624, 0x2625), (0x2627, 0x2629), (0x262b, 0x262d), (0x2630, 0x2637), (0x263b, 0x2647), (0x2654, 0x265f), (0x2661, 0x2662), (0x2664, 0x2665), (0x2667, 0x2668), (0x2669, 0x267a), (0x267c, 0x267e), (0x2680, 0x2691), (0x2695, 0x2696), (0x2698, 0x2699), (0x269a, 0x269b), (0x269d, 0x269f), (0x26a2, 0x26a9), (0x26ac, 0x26af), (0x26b2, 0x26bc), (0x26bf, 0x26c3), (0x26c6, 0x26c7), (0x26c9, 0x26cd), (0x26d0, 0x26d1), (0x26d2, 0x26d3), (0x26d5, 0x26e8), (0x26eb, 0x26ef), (0x26f6, 0x26f7), (0x26fb, 0x26fc), (0x26fe, 0x26ff), (0x2700, 0x2701), (0x2703, 0x2704), (0x270e, 0x270f), (0x2710, 0x2711), (0x2765, 0x2767), (0x1f000, 0x1f003), (0x1f005, 0x1f02b), (0x1f02c, 0x1f02f), (0x1f030, 0x1f093), (0x1f094, 0x1f09f), (0x1f0a0, 0x1f0ae), (0x1f0af, 0x1f0b0), (0x1f0b1, 0x1f0bf), (0x1f0c0, 0x1f0c1), (0x1f0c1, 0x1f0cf), (0x1f0d0, 0x1f0d1), (0x1f0d1, 0x1f0f5), (0x1f0f6, 0x1f0ff), (0x1f10d, 0x1f10f), (0x1f12f, 0x1f130), (0x1f16c, 0x1f16f), (0x1f1ad, 0x1f1e5), (0x1f203, 0x1f20f), (0x1f23c, 0x1f23f), (0x1f249, 0x1f24f), (0x1f252, 0x1f25f), (0x1f260, 0x1f265), (0x1f266, 0x1f2ff), (0x1f322, 0x1f323), (0x1f394, 0x1f395), (0x1f398, 0x1f399), (0x1f39c, 0x1f39d), (0x1f3f1, 0x1f3f2), (0x1f3f6, 0x1f3f7), (0x1f4fe, 0x1f4ff), (0x1f53e, 0x1f548), (0x1f54f, 0x1f550), (0x1f568, 0x1f56e), (0x1f571, 0x1f572), (0x1f57b, 0x1f586), (0x1f588, 0x1f589), (0x1f58e, 0x1f58f), (0x1f591, 0x1f594), (0x1f597, 0x1f5a3), (0x1f5a6, 0x1f5a7), (0x1f5a9, 0x1f5b0), (0x1f5b3, 0x1f5bb), (0x1f5bd, 0x1f5c1), (0x1f5c5, 0x1f5d0), (0x1f5d4, 0x1f5db), (0x1f5df, 0x1f5e0), (0x1f5e2, 0x1f5e3), (0x1f5e4, 0x1f5e7), (0x1f5e9, 0x1f5ee), (0x1f5f0, 0x1f5f2), (0x1f5f4, 0x1f5f9), (0x1f6c6, 0x1f6ca), (0x1f6d3, 0x1f6d4), (0x1f6d5, 0x1f6df), (0x1f6e6, 0x1f6e8), (0x1f6ea, 0x1f6eb), (0x1f6ed, 0x1f6ef), (0x1f6f1, 0x1f6f2), (0x1f6f7, 0x1f6f8), (0x1f6f9, 0x1f6ff), (0x1f774, 0x1f77f), (0x1f7d5, 0x1f7ff), (0x1f80c, 0x1f80f), (0x1f848, 0x1f84f), (0x1f85a, 0x1f85f), (0x1f888, 0x1f88f), (0x1f8ae, 0x1f8ff), (0x1f900, 0x1f90b), (0x1f90c, 0x1f90f), (0x1f91f, 0x1f920), (0x1f928, 0x1f92f), (0x1f931, 0x1f932), (0x1f93f, 0x1f940), (0x1f94c, 0x1f94d), (0x1f94d, 0x1f94f), (0x1f95f, 0x1f96b), (0x1f96c, 0x1f97f), (0x1f992, 0x1f997), (0x1f998, 0x1f9bf), (0x1f9c1, 0x1f9cf), (0x1f9d0, 0x1f9e6), (0x1f9e7, 0x1f9ff), (0x1fa00, 0x1fffd)]
                    return ranges if escaped == 'p' else multirange_diff(graph.charsets[dot_charset], ranges), offset

                codepoints = None
                # [\\p{GCB=Regional_Indicator}\\*#0-9\\u00a9\\u00ae\\u2122\\u3030\\u303d]
                if prop_name in ['EmojiRK', 'EmojiNRK']:
                    emoji_rk_codepoints = _name_to_codepoints(r'\p{GCB=Regional_Indicator}')
                    emoji_rk_codepoints.extend([ord(c) for c in ['*', '#', '\u00a9', '\u00ae', '\u2122', '\u3030', '\u303d'] + list(map(str, range(10)))])
                    if prop_name == 'EmojiRK':
                        codepoints = emoji_rk_codepoints
                    else:
                        # [\\p{Emoji=Yes}] - EmojiRK
                        codepoints = set(_name_to_codepoints(r'\p{Emoji=Yes}')) - set(emoji_rk_codepoints)
                # [[\\p{Emoji=Yes}]&[\\p{Emoji_Presentation=Yes}]]
                elif prop_name == 'EmojiPresentation=EmojiDefault':
                    codepoints = set(_name_to_codepoints(r'\p{Emoji=Yes}')) & set(_name_to_codepoints(r'\p{Emoji_Presentation=Yes}'))
                # [[\\p{Emoji=Yes}]&[\\p{Emoji_Presentation=No}]]
                elif prop_name == 'EmojiPresentation=TextDefault':
                    codepoints = set(_name_to_codepoints(r'\p{Emoji=Yes}')) & set(_name_to_codepoints(r'\p{Emoji_Presentation=No}'))
                # [\\p{Emoji=No}]
                elif prop_name == 'EmojiPresentation=Text':
                    codepoints = _name_to_codepoints(r'\p{Emoji=No}')

                if codepoints:
                    ranges = _codepoints_to_ranges(codepoints)
                    return ranges if escaped == 'p' else multirange_diff(graph.charsets[dot_charset], ranges), offset

                # \p{...} and \P{...} are both handled by the regex lib in case of the supported properties.
                return _codepoints_to_ranges(_name_to_codepoints(f'\\{escaped}{{{prop_name}}}')), offset

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

        def lexer_charset_interval(s: str) -> list[tuple[int, int]]:
            # To be kept in sync with org.antlr.v4.automata.LexerATNFactory.getSetFromCharSetLiteral
            assert len(s) > 0, 'Charset cannot be empty'

            ranges = []

            offset = 0
            while offset < len(s):
                in_range = s[offset] == '-' and offset != 0 and offset != len(s) - 1
                if in_range:
                    offset += 1

                codepoint, offset = process_lexer_char(s, offset, 'lexer charset')

                if isinstance(codepoint, list):
                    if in_range or (offset < len(s) - 1 and s[offset] == '-'):
                        raise ValueError(f'Unicode property escapes are not allowed in lexer charset range ({s})')
                    ranges.extend(codepoint)
                elif in_range:
                    ranges[-1] = (ranges[-1][0], codepoint + 1)
                else:
                    ranges.append((codepoint, codepoint + 1))

            return ranges

        def chars_from_set(node: RuleContext) -> list[tuple[int, int]]:
            if node.characterRange():
                return [character_range_interval(node)]

            if node.LEXER_CHAR_SET():
                return lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])

            if node.STRING_LITERAL():
                char = str(node.STRING_LITERAL())[1:-1]
                char_cp, char_offset = process_lexer_char(char, 0, 'not set literal')
                assert isinstance(char_cp, int), 'String literal in not set cannot be a list of codepoints.'
                if char_offset < len(char):
                    raise ValueError(f'Zero or multi-character literals are not allowed in lexer sets: {char!r}')
                return [(char_cp, char_cp + 1)]

            if node.TOKEN_REF():
                src = str(node.TOKEN_REF())
                assert graph.vertices[src].start_ranges is not None, f'{src} has no character start ranges.'
                return graph.vertices[src].start_ranges

            return []

        def unique_charset(ranges: list[tuple[int, int]]) -> int:
            if not ranges:
                raise ValueError('Charset must contain at least one range')
            for start, end in ranges:
                if end <= start:
                    raise ValueError(f"Charset range must not be empty: '\\u{{{start:x}}}'..'\\u{{{end - 1:x}}}', '{chr(start)}'..'{chr(end - 1)}'")

            return append_unique(graph.charsets, ranges)

        def unescape_string(s: str) -> str:
            def _iter_unescaped_chars(s: str) -> Generator[str]:
                offset = 0
                while offset < len(s):
                    codepoint, offset = process_lexer_char(s, offset, 'string literal')
                    assert isinstance(codepoint, int), 'String literal cannot start with unicode property.'
                    yield chr(codepoint)

            return ''.join(c for c in _iter_unescaped_chars(s))

        def parse_arg_action_block(node: RuleContext, use_case: str) -> list[EdgeArgType]:
            args = []

            def _save_pair(k, v):
                # If we don't have both left and right handside, then the provided
                # single value will be handled as if it were a variable name, except
                # for the `call` use case, where it will be handled as a value.
                if use_case != 'call' and k is None:
                    k, v = v, None
                t = None
                if k:
                    m = re.fullmatch(r'(\w+)\s*:([^:].*)', k)  # postfix type notation (name: type)
                    if m:
                        t, k = m.group(2, 1)
                        t = t.strip()
                    else:
                        m = re.fullmatch(r'(.+)\s+(\w+)', k)  # prefix type notation (type name)
                        if m:
                            t, k = m.group(1, 2)
                            t = t.strip()
                        else:
                            m = re.fullmatch(r'(\w+)', k)  # no-type notation (name)
                            if not m:
                                raise ValueError(f'unsupported type notation {k} in {use_case}')
                if t == '':
                    raise ValueError(f'type in {use_case} must not be empty')
                if k == '':
                    raise ValueError(f'name in {use_case} must not be empty')
                if v == '':
                    raise ValueError(f'value in {use_case} must not be empty')
                args.append((t, k, v))

            if node and node.argActionBlock():
                src = ''.join(str(chr_arg) for chr_arg in node.argActionBlock().ARGUMENT_CONTENT()).strip()
                pairs: Counter[str] = Counter()
                start, offset, end = 0, 0, len(src)
                lhs = None
                # Find the argument boundaries.
                while offset < end:
                    c = src[offset]
                    if c in ['\'', '"']:
                        offset += 1
                        while offset < end and src[offset] != c:
                            if src[offset] == '\\' and offset + 1 < end and src[offset + 1] == c:
                                offset += 1  # Skip \
                            offset += 1  # Skip a non-quote/apostrophe or an escaped quote/apostrophe
                    elif c in ['(', '[', '{']:
                        pairs[c] += 1
                    elif c in [')', ']', '}']:
                        pairs[c] -= 1
                    elif c == ',':
                        if sum(pairs.values()) == 0:
                            _save_pair(lhs, src[start:offset].strip())
                            start = offset + 1
                            lhs = None
                    elif offset < end - 1 and src[offset:offset + 2] in ['==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=', '^=', ':=']:
                        offset += 1
                    elif c == '=' and lhs is None:
                        lhs = src[start:offset].strip()
                        start = offset + 1
                    offset += 1

                if sum(pairs.values()) != 0:
                    raise ValueError(f'Non-matching pairs in action ({",".join((k for k, v in pairs.items() if v > 0))})')

                _save_pair(lhs, src[start:].strip())
            return args

        def isfloat(s: str):
            try:
                float(s)
                return True
            except ValueError:
                return False

        # TODO: Typing of build_rule is a nightmare, hence it's postponed.
        def build_rule(rule, node):
            lexer_rule = isinstance(rule, UnlexerRuleNode)

            def build_expr(node, parent_id):
                if isinstance(node, ANTLRv4Parser.ParserRuleSpecContext):
                    if actions:
                        rule.args = parse_arg_action_block(node, 'args')
                        rule.locals = parse_arg_action_block(node.localsSpec(), 'locals')
                        rule.returns = parse_arg_action_block(node.ruleReturns(), 'returns')

                        for prequel in node.rulePrequel() or []:
                            rule_action = prequel.ruleAction()
                            if rule_action:
                                action_name = str(rule_action.identifier().TOKEN_REF() or rule_action.identifier().RULE_REF())
                                if action_name not in ['init', 'after']:
                                    continue

                                src = ''.join(str(child) for child in rule_action.actionBlock().ACTION_CONTENT()).strip()
                                if action_name == 'init':
                                    rule.init = src
                                elif action_name == 'after':
                                    rule.after = src
                    build_expr(node.ruleBlock(), parent_id)

                elif isinstance(node, (ANTLRv4Parser.RuleAltListContext, ANTLRv4Parser.AltListContext, ANTLRv4Parser.LexerAltListContext)):
                    children = [child for child in node.children if isinstance(child, ParserRuleContext)]
                    if len(children) == 1:
                        build_expr(children[0], parent_id)
                        return

                    conditions = [find_conditions(child) for child in children]
                    labels = [str(child.identifier().TOKEN_REF() or child.identifier().RULE_REF()) for child in children if child.identifier()] if isinstance(node, ANTLRv4Parser.RuleAltListContext) else []
                    # Ensure to start labels with capital letter, since ANTLR will also create a context with capital start character.
                    # It's important to keep them in sync since grammarinator-parse will use this graph for comparison.
                    labels = [label[0].upper() + label[1:] for label in labels]
                    recurring_labels = {name for name, cnt in Counter(labels).items() if cnt > 1}
                    assert len(labels) == 0 or len(labels) == len(children)
                    alt_id = graph.add_node(AlternationNode(idx=alt_idx[rule.name], conditions=append_unique(graph.alt_conds, conditions) if all(isfloat(cond) for cond in conditions) else conditions, rule_id=rule.id))
                    alt_idx[rule.name] += 1
                    graph.add_edge(frm=parent_id, to=alt_id)

                    for i, child in enumerate(children):
                        alternative_id = graph.add_node(AlternativeNode(rule_id=rule.id, alt_idx=graph.vertices[alt_id].idx, idx=i))
                        graph.add_edge(frm=alt_id, to=alternative_id)

                        if labels:
                            # Add label index to rules to distinguish the alternatives with recurring labels.
                            label_idx = labels[:i + 1].count(labels[i]) - 1 if labels[i] in recurring_labels else None
                            rule_node_id = graph.add_node(UnparserRuleNode(name=(rule.name, labels[i], label_idx) if label_idx is not None else (rule.name, labels[i])))
                            graph.add_edge(frm=alternative_id, to=rule_node_id)
                            build_rule(graph.vertices[rule_node_id], child)
                        else:
                            build_expr(child, alternative_id)

                    # Add an artificial rule named `{rule.name}_{label}` that has a single alternation with
                    # the original number of alternatives which are however masked to enable to choose only
                    # those labeled with `label`. This method will be used to regenerate the subtrees produced
                    # by a labelled alternative with recurring label name.
                    for label in recurring_labels:
                        # Mask conditions to enable only the alternatives with the common label.
                        new_conditions = [cond if labels[ci] == label else '0' for ci, cond in enumerate(conditions)]
                        recurring_rule_id = graph.add_node(UnparserRuleNode(name=(rule.name, label), trampoline=True))
                        labeled_alt_id = graph.add_node(AlternationNode(idx=0,
                                                                        conditions=append_unique(graph.alt_conds, new_conditions) if all(isfloat(cond) for cond in new_conditions) else new_conditions,
                                                                        rule_id=recurring_rule_id))
                        graph.add_edge(frm=recurring_rule_id, to=labeled_alt_id)
                        recurring_idx = 0
                        for i in range(len(children)):
                            labeled_alternative_id = graph.add_node(AlternativeNode(rule_id=recurring_rule_id, alt_idx=0, idx=i))
                            graph.add_edge(frm=labeled_alt_id, to=labeled_alternative_id)
                            if labels[i] == label:
                                graph.add_edge(frm=labeled_alternative_id, to=(rule.name, label, recurring_idx))
                                recurring_idx += 1
                            else:
                                graph.add_edge(frm=labeled_alternative_id, to=lambda_id)

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

                    suffix = str(suffix.children[0])
                    quant_ranges = {'?': {'start': 0, 'stop': 1}, '*': {'start': 0, 'stop': inf}, '+': {'start': 1, 'stop': inf}}
                    quant_id = graph.add_node(QuantifierNode(rule_id=rule.id, idx=quant_idx[rule.name], **quant_ranges[suffix]))
                    quant_idx[rule.name] += 1
                    graph.add_edge(frm=parent_id, to=quant_id)
                    build_expr(node.children[0], quant_id)

                elif isinstance(node, ANTLRv4Parser.LabeledElementContext):
                    build_expr(node.atom() or node.block(), parent_id)
                    # Do not save variables if actions are not allowed.
                    if not actions:
                        return

                    ident = node.identifier()
                    name = str(ident.RULE_REF() or ident.TOKEN_REF())
                    is_list = node.PLUS_ASSIGN() is not None
                    graph.add_edge(frm=parent_id, to=graph.add_node(VariableNode(name=name, is_list=is_list)))
                    rule.labels[name] = is_list

                elif isinstance(node, ANTLRv4Parser.RulerefContext):
                    graph.add_edge(frm=parent_id, to=str(node.RULE_REF()), args=parse_arg_action_block(node, 'call') if actions else None)

                elif isinstance(node, (ANTLRv4Parser.LexerAtomContext, ANTLRv4Parser.AtomContext)):
                    if node.DOT():
                        if isinstance(node, ANTLRv4Parser.LexerAtomContext):
                            graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.id, idx=chr_idx[rule.name], charset=dot_charset)))
                            chr_idx[rule.name] += 1
                        else:
                            if '_dot' not in graph.vertices:
                                # Create an artificial `_dot` rule with an alternation of all the lexer rules.
                                parser_dot_id = graph.add_node(UnparserRuleNode(name='_dot'))
                                unlexer_ids = [v.name for vid, v in graph.vertices.items() if isinstance(v, UnlexerRuleNode)]
                                alt_id = graph.add_node(AlternationNode(rule_id=parser_dot_id, idx=0, conditions=[1] * len(unlexer_ids)))
                                graph.add_edge(frm=parser_dot_id, to=alt_id)
                                for i, lexer_id in enumerate(unlexer_ids):
                                    alternative_id = graph.add_node(AlternativeNode(rule_id=parser_dot_id, alt_idx=0, idx=i))
                                    graph.add_edge(frm=alt_id, to=alternative_id)
                                    graph.add_edge(frm=alternative_id, to=lexer_id)
                            graph.add_edge(frm=parent_id, to='_dot')

                    elif node.notSet():
                        if node.notSet().setElement():
                            not_ranges = chars_from_set(node.notSet().setElement())
                        else:
                            not_ranges = []
                            for set_element in node.notSet().blockSet().setElement():
                                not_ranges.extend(chars_from_set(set_element))

                        charset = unique_charset(multirange_diff(graph.charsets[dot_charset], sorted(not_ranges, key=lambda x: x[0])))
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.id, idx=chr_idx[rule.name], charset=charset)))
                        chr_idx[rule.name] += 1

                    elif isinstance(node, ANTLRv4Parser.LexerAtomContext) and node.characterRange():
                        start, end = character_range_interval(node)
                        if lexer_rule:
                            rule.start_ranges.append((start, end))

                        charset = unique_charset([(start, end)])
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.id, idx=chr_idx[rule.name], charset=charset)))
                        chr_idx[rule.name] += 1

                    elif isinstance(node, ANTLRv4Parser.LexerAtomContext) and node.LEXER_CHAR_SET():
                        ranges = lexer_charset_interval(str(node.LEXER_CHAR_SET())[1:-1])
                        if lexer_rule:
                            rule.start_ranges.extend(ranges)

                        charset = unique_charset(sorted(ranges, key=lambda x: x[0]))
                        graph.add_edge(frm=parent_id, to=graph.add_node(CharsetNode(rule_id=rule.id, idx=chr_idx[rule.name], charset=charset)))
                        chr_idx[rule.name] += 1

                    for child in node.children:
                        build_expr(child, parent_id)

                elif isinstance(node, ANTLRv4Parser.TerminalContext):
                    if node.TOKEN_REF():
                        if str(node.TOKEN_REF()) != 'EOF':
                            graph.add_edge(frm=parent_id, to=str(node.TOKEN_REF()))

                    elif node.STRING_LITERAL():
                        src = unescape_string(str(node.STRING_LITERAL())[1:-1])

                        if lexer_rule:
                            rule.start_ranges.append((ord(src[0]), ord(src[0]) + 1))
                            graph.add_edge(frm=parent_id, to=graph.add_node(LiteralNode(src=src)))
                        else:
                            # Ensure that every inline literal in parser rules has its lexer rule
                            # found or implicitly created.
                            lit_id = literal_lookup.get(src)
                            if not lit_id:
                                lit_id = graph.add_node(UnlexerRuleNode())
                                literal_lookup[src] = lit_id
                                graph.add_edge(frm=lit_id, to=graph.add_node(LiteralNode(src=src)))
                            graph.add_edge(frm=parent_id, to=lit_id)

                elif isinstance(node, ParserRuleContext) and node.getChildCount():
                    for child in node.children:
                        build_expr(child, parent_id)

            if lexer_rule:
                rule.start_ranges = []

            build_expr(node, rule.id)

            # Save lexer rules with constant literals to enable resolving them in parser rules.
            if lexer_rule and len(rule.out_edges) == 1 and isinstance(rule.out_edges[0].dst, LiteralNode):
                literal_lookup[rule.out_edges[0].dst.src] = rule.id

        def build_prequel(node: ANTLRv4Parser.GrammarSpecContext):
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

        def build_rules(node: RuleContext):
            generator_rules, duplicate_rules = [], []
            for rule in node.rules().ruleSpec():
                if rule.parserRuleSpec():
                    rule_spec = rule.parserRuleSpec()
                    rule_node: RuleNode = UnparserRuleNode(name=str(rule_spec.RULE_REF()))
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
                raise ValueError(f'Rule redefinition(s): {", ".join(["_".join(id) for id in duplicate_rules])}')  # type: ignore[arg-type]

            # Ensure to process lexer rules first to lookup table from literal constants.
            for rule_args in sorted(generator_rules, key=lambda r: int(isinstance(r[0], UnparserRuleNode))):
                build_rule(*rule_args)

            if default_rule:
                graph.default_rule = default_rule
            elif node.grammarDecl().grammarType().PARSER() or not (node.grammarDecl().grammarType().LEXER() or node.grammarDecl().grammarType().PARSER()):
                graph.default_rule = generator_rules[0][0].name  # type: ignore[assignment]

        graph = GrammarGraph()
        lambda_id = graph.add_node(LambdaNode())

        for root in [lexer_root, parser_root]:
            if root:
                build_prequel(root)
        graph.options.update(options or {})

        dot_charset = unique_charset(dot_ranges[graph.dot])

        literal_lookup: dict[str, NodeIdType] = {}
        alt_idx: Counter[str] = Counter()
        quant_idx: Counter[str] = Counter()
        chr_idx: Counter[str] = Counter()

        for root in [lexer_root, parser_root]:
            if root:
                build_rules(root)

        graph.calc_min_sizes()
        graph.find_immutable_rules()
        return graph

    # Calculates the distance of every rule node from the start node. As a result, it can
    # point out to rules, that are not available from there, furthermore it can give a hint
    # about the farthest node/rule to help to determine a max_depth that has the chance to
    # reach every rule. Also checks for infinite derivations.
    @staticmethod
    def _analyze_graph(graph: GrammarGraph, root: Optional[str] = None) -> None:
        root_id: str = root or graph.default_rule
        min_distances: dict[NodeIdType, Union[int, float]] = defaultdict(lambda: inf)
        min_distances[(root_id,)] = 0

        work_list = [(root_id,)]
        while work_list:
            v = work_list.pop(0)
            for out_v in graph.vertices[v].out_neighbours:
                d = min_distances[v] + int(isinstance(out_v, RuleNode))
                if d < min_distances[out_v.id]:
                    min_distances[out_v.id] = d
                    work_list.append(out_v.id)

        farthest_ident, max_distance = max(((v_id, d) for v_id, d in min_distances.items() if (isinstance(graph.vertices[v_id], RuleNode) and d != inf)), key=lambda item: item[1])
        unreachable_rules = [v_id for v_id, v in graph.vertices.items() if isinstance(v, RuleNode) and min_distances[v_id] == inf]

        logger.info('\tThe farthest rule from %r is %r (%d step(s)).', root_id, '_'.join(farthest_ident), max_distance)  # type: ignore[arg-type]
        if unreachable_rules:
            logger.warning('\t%d rule(s) unreachable from %r: %s', len(unreachable_rules), root_id, ', '.join(repr('_'.join(unreachable_rule)) for unreachable_rule in unreachable_rules))

        inf_alts = []
        inf_rules = []
        for ident, node in graph.vertices.items():
            if isinstance(node, AlternationNode):
                for alternative_idx, alternative_node in enumerate(node.out_neighbours):
                    if graph.alt_sizes[node.min_sizes][alternative_idx].depth == inf:
                        # Generate human-readable description for an alternative in the graph. The output is a
                        # (rule node, alternation node, alternative node) string, where `rule` defines the container
                        # rule and the (alternation node, alternative node) sequence defines a derivation reaching the alternative.
                        inf_alts.append(f'({graph.vertices[alternative_node.rule_id].name!r}, {node.idx}, {alternative_node.idx})')  # type: ignore[attr-defined]
            elif isinstance(node, RuleNode):
                if node.min_size.depth == inf:
                    inf_rules.append(ident)
        if inf_alts:
            logger.warning('\t%d alternative(s) with infinite derivation (rule, alternation, alternative):\n\t\t%s', len(inf_alts), ',\n\t\t'.join(inf_alts))
        if inf_rules:
            logger.warning('\t%d rule(s) with infinite derivation (possible cycles): %s', len(inf_rules), ', '.join(repr('_'.join(inf_rule)) for inf_rule in inf_rules))
