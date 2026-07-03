# Copyright (c) 2017-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from __future__ import annotations

from .model import AlternationNode, AlternativeNode, Edge, FragmentRefNode, FragmentRuleNode, GrammarGraph, Node, QuantifierNode


# CPython caps the number of statically-nested blocks (`with`/`while`/`for`/`try`;
# `if`/`elif` do not count) per code object at CO_MAXBLOCKS. 3.14 tolerates 21,
# but older supported interpreters enforce the historical value of 20, so stay
# conservative and portable.
MAX_BLOCKS = 20


def _block_cost(node: Node) -> int:
    # Blocks a node opens in the rendered Python method. Must mirror
    # GeneratorTemplate.py.jinja exactly: a quantifier emits `with` + `while` +
    # `with` (3), an alternation emits a single `with` (its branches are
    # `if`/`elif`, which cost nothing), everything else emits no block.
    #
    # NOTE: user action code (``@init``, ``@after``, ``@locals`` etc.) is NOT
    # counted here. If action code contains Python block statements (`with`,
    # `for`, `while`, `try`, `if`) and the surrounding grammar rule is already
    # deeply nested, the combined nesting may still exceed CO_MAXBLOCKS and
    # trigger a ``SyntaxError`` at import time without a split being triggered.
    # This is a known limitation for action-heavy grammars.
    if isinstance(node, QuantifierNode):
        return 3
    if isinstance(node, AlternationNode):
        return 1
    return 0


def _inlined_children(node: Node) -> list[Edge]:
    # The renderer only inlines (and thus nests blocks through) quantifiers,
    # alternations and alternatives. Rule references are emitted as separate
    # method calls (`self.foo(...)`), so they -- and all leaves -- stop the walk.
    if isinstance(node, (QuantifierNode, AlternationNode, AlternativeNode)):
        return node.out_edges
    return []


def _subtree_depth(node: Node, base: int) -> int:
    # Max block nesting reached within `node`'s subtree, given `base` blocks are
    # already open around it.
    nb = base + _block_cost(node)
    return max([nb] + [_subtree_depth(edge.dst, nb) for edge in _inlined_children(node)])


def _method_depth(out_edges: list[Edge], base: int) -> int:
    return max([base] + [_subtree_depth(edge.dst, base) for edge in out_edges])


def _deepest_cut(out_edges: list[Edge], base: int) -> tuple[list[Edge], int] | None:
    # Find the deepest inlined block node whose subtree overflows MAX_BLOCKS while
    # its own position is still within budget, and return the (containing edge
    # list, index) to cut. Cutting the deepest keeps each extracted fragment
    # minimal and guarantees progress. Returns None when the body needs no cut.
    best: tuple[int, list[Edge], int] | None = None

    def walk(edges: list[Edge], node_base: int) -> None:
        nonlocal best
        for idx, edge in enumerate(edges):
            node = edge.dst
            cost = _block_cost(node)
            if cost and node_base <= MAX_BLOCKS and _subtree_depth(node, node_base) > MAX_BLOCKS and (best is None or node_base > best[0]):
                best = (node_base, edges, idx)
            walk(_inlined_children(node), node_base + cost)

    walk(out_edges, base)
    return (best[1], best[2]) if best else None


# Split any rule whose block nesting would exceed CPython's CO_MAXBLOCKS
# limit into synthetic fragment helper methods. Grammarinator renders every
# rule as one Python method, inlining sub-structure recursively; each
# quantifier opens 3 nested blocks and each alternation 1 (see `_block_cost`,
# which MUST stay in sync with GeneratorTemplate.py.jinja). Deeply nested
# quantifiers/alternations therefore overflow the limit and make the
# generated module raise `SyntaxError: too many statically nested blocks` at
# import. We cut the deepest over-budget node into a `def` (block depth 0)
# and leave a call behind; extraction is safe because `current == rule.current`
# at every sibling position. Python target only -- C++ has no such limit.
def split_deep_rules(graph: GrammarGraph) -> None:
    for rule in graph.rules:
        # Per-rule state shared by every fragment carved out of this rule: the
        # base name (rule id with leading underscores stripped, to dodge
        # CPython's `__name` -> `_Class__name` mangling) and a fragment
        # counter. A FIFO work list drives repeated cuts -- the current body
        # stays at the front until fully split, then each new fragment (base
        # 0) is split in creation order, keeping names/output stable.
        base_name = '_'.join(str(part) for part in rule.id).lstrip('_')
        counter = 0
        work_list: list[tuple[list[Edge], int]] = [(rule.out_edges, 1)]
        while work_list:
            out_edges, base = work_list[0]
            cut = _deepest_cut(out_edges, base)
            if cut is None:
                if _method_depth(out_edges, base) > MAX_BLOCKS:
                    raise RuntimeError(f'Rule {base_name!r} exceeds the {MAX_BLOCKS}-block limit but no valid cut was found (block-cost table out of sync with the template?).')
                work_list.pop(0)
                continue
            edges, idx = cut
            method_name = f'_{base_name}_frag_{counter}'
            counter += 1
            graph.fragments.append(FragmentRuleNode(method_name=method_name, has_local_ctx=rule.has_local_ctx, edge=edges[idx]))
            edges[idx] = Edge(dst=FragmentRefNode(method_name=method_name, has_local_ctx=rule.has_local_ctx))
            work_list.append((graph.fragments[-1].out_edges, 0))
