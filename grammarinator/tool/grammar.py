# Copyright (c) 2017-2026 Renata Hodovan, Akos Kiss.
# Copyright (c) 2020 Sebastian Kimberk.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from __future__ import annotations

from collections import defaultdict, OrderedDict
from itertools import chain
from math import inf
from sys import maxunicode
from typing import ClassVar, DefaultDict, Generator


EdgeArgType = list[tuple[str | None, str | None, str | None]]
RuleIdType = str | tuple[str] | tuple[str, str] | tuple[str, str, int]
NodeIdKeyType = RuleIdType | tuple[int] | tuple[int, str, int]
NodeIdType = NodeIdKeyType | tuple[NodeIdKeyType, str, int] | tuple[NodeIdKeyType, str, int, int]


class Edge:

    def __init__(self, dst: Node, args: EdgeArgType | None = None) -> None:
        self.dst = dst
        self.args = args
        self.reserve: int = 0


class Node:

    _cnt: ClassVar[int] = 0

    def __init__(self, id: NodeIdType | None = None) -> None:
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

    def __init__(self, depth: int | float, tokens: int | float) -> None:
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
        self.options: dict[str, str] = {}

    @property
    def has_local_ctx(self) -> bool:
        return bool(self.labels or self.args or self.locals or self.returns)

    def __str__(self) -> str:
        return f'{super().__str__()}; name: {self.id}'


class OutlinedNode(Node):

    def __init__(self, node: AlternationNode | QuantifierNode, rule: RuleNode) -> None:
        super().__init__()
        # Avoid `__name` class mangling for rules with leading underscores.
        rule_name = '_'.join(str(part) for part in rule.id).lstrip('_')
        node_name = 'quant' if isinstance(node, QuantifierNode) else 'alt'
        self.name = f'_{rule_name}_{node_name}{node.idx}'
        self.has_local_ctx = rule.has_local_ctx
        self.out_edges = [Edge(node)]


class UnlexerRuleNode(RuleNode):

    _lit_cnt: ClassVar[int] = 0

    def __init__(self, name: str | None = None) -> None:
        if not name:
            name = f'T__{UnlexerRuleNode._lit_cnt}'
            UnlexerRuleNode._lit_cnt += 1
        super().__init__(name, 'UnlexerRule')
        self.start_ranges: list[tuple[int, int]] | None = None


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

    def simple_alternatives(self) -> tuple[list[str | None] | None, list[NodeIdType | None] | None]:
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

        lits_list: list[str | None] = [
            alt.out_neighbours[0].src if isinstance(alt.out_neighbours[0], LiteralNode) else None
            for alt in self.out_neighbours
        ]
        rules_list: list[NodeIdType | None] = [
            alt.out_neighbours[0].id if isinstance(alt.out_neighbours[0], RuleNode) else None
            for alt in self.out_neighbours
        ]

        simple_lits: list[str | None] | None = None if all(x is None for x in lits_list) else lits_list
        simple_rules: list[NodeIdType | None] | None = None if all(x is None for x in rules_list) else rules_list

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

    def __init__(self, rule_id: RuleIdType, idx: int, start: int, stop: int | float) -> None:
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
        self.outlined: list[OutlinedNode] = []
        self.alt_conds: list[AlternationNode] = []
        self.alt_sizes: list[list[NodeSize]] = []
        self.quant_sizes: list[NodeSize] = []
        self.immutables: list[NodeIdType] | None = None
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

    def print_tree(self, root: Node | None = None) -> None:
        if not root and not self.default_rule:
            raise ValueError('Either `root` must be defined or `print_tree` should be called after `default_rule` is set.')
        (root or self.vertices[(self.default_rule,)]).print_tree()

    def add_node(self, node: Node) -> NodeIdType:
        self.vertices[node.id] = node
        return node.id

    def add_edge(self, frm: NodeIdType, to: NodeIdType, args: EdgeArgType | None = None) -> None:
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
            reserve: int | float = 0
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
