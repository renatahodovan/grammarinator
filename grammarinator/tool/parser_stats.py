# Copyright (c) 2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import math
import struct

from collections import Counter, defaultdict
from statistics import median

import xxhash

from ..runtime import Annotations, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantifier
from .grammar import AlternationNode, AlternativeNode, QuantifierNode, RuleNode, UnparserRuleNode
from .tree_codec import AnnotatedTreeCodec

# Detailed per-file measurements that are merged into the corpus statistics
# instead of being kept for every file.
_MERGED_FIELDS = ('rules', 'alternatives', 'quantifiers', 'pool', 'self_embedding', 'self_nesting', 'lexer_values', 'k_paths')


# Gather tree measurements and subtree hashes (for deduplication) in one postorder walk.
def collect_tree_stats(root, codec):
    annotations = Annotations(root)
    keys = {node: key for key, nodes in annotations.nodes_by_name.items() for node in nodes}
    keys[root] = (root.name,)
    result = {'_final_depth': annotations.node_depths[root], '_final_tokens': annotations.node_tokens[root],
              'nodes': 0, 'rules': Counter(), 'alternatives': Counter(), 'quantifiers': defaultdict(list),
              'pool': defaultdict(set), 'self_embedding': {}, 'self_nesting': {}, 'lexer_values': defaultdict(Counter)}
    result['k_paths'] = {2: set(), 3: set()}
    wrappers = {}
    path = Counter()

    # Hash each node after its children, while tracking rule paths and unit chains.
    def walk(node, owner, ancestors, rule_path=()):
        result['nodes'] += 1
        if isinstance(node, (UnparserRule, UnlexerRule)):
            owner = node.name
            rule_path += (owner,)
            for size in (2, 3):
                if len(rule_path) >= size:
                    result['k_paths'][size].add(rule_path[-size:])
            result['rules'][owner] += 1
            path[owner] += 1
            result['self_nesting'][owner] = max(result['self_nesting'].get(owner, 0), path[owner])
            for ancestor in ancestors:
                if isinstance(node, UnparserRule) and ancestor.name == owner:
                    level = annotations.node_levels[node] - annotations.node_levels[ancestor]
                    tokens = annotations.node_tokens[ancestor] - annotations.node_tokens[node]
                    old = wrappers.setdefault(ancestor, [math.inf, math.inf])
                    old[0], old[1] = min(old[0], level), min(old[1], tokens)
            if isinstance(node, UnlexerRule):
                result['lexer_values'][owner][node.src] += 1
        if isinstance(node, UnparserRuleAlternative):
            result['alternatives'][f'{owner}|{node.alt_idx}|{node.idx}'] += 1
        elif isinstance(node, UnparserRuleQuantifier):
            result['quantifiers'][f'{owner}|{node.idx}'].append(len(node.children))

        kind = ('l' if isinstance(node, UnlexerRule) else 'p' if isinstance(node, UnparserRule) else
                'a' if isinstance(node, UnparserRuleAlternative) else 'q' if isinstance(node, UnparserRuleQuantifier) else 'd')
        digest = xxhash.xxh64(kind.encode(), seed=0)
        if isinstance(node, UnlexerRule):
            digest.update(node.name.encode())
            digest.update(node.src.encode())
            digest.update(struct.pack('=ii?', int(node.size.depth), int(node.size.tokens), node.immutable))
            nesting = node.size.depth
        else:
            if isinstance(node, UnparserRule):
                digest.update(node.name.encode())
            elif isinstance(node, UnparserRuleAlternative):
                digest.update(owner.encode())
                digest.update(struct.pack('=ii', node.alt_idx, node.idx))
            elif isinstance(node, UnparserRuleQuantifier):
                digest.update(owner.encode())
                digest.update(struct.pack('=iii', node.idx, node.start, -1 if math.isinf(node.stop) else node.stop))
            else:
                digest.update(owner.encode())
                digest.update(struct.pack('=i', node.parent.idx))
            digest.update(b'(')
            child_nesting = []
            next_ancestors = ancestors + (node,) if isinstance(node, UnparserRule) else ancestors
            for child in node.children:
                child_hash, child_depth = walk(child, owner, next_ancestors, rule_path)
                digest.update(struct.pack('=Q', child_hash))
                digest.update(b',')
                child_nesting.append(child_depth)
            digest.update(b')')
            nesting = max(child_nesting, default=0)
            if isinstance(node, UnparserRule):
                direct = list(node.children)
                content = []
                while direct and len(content) < 2:
                    child = direct.pop()
                    if isinstance(child, (UnparserRule, UnlexerRule)):
                        content.append(child)
                    else:
                        direct.extend(child.children)
                if len(content) != 1 or not isinstance(content[0], UnparserRule):
                    nesting += 1

        hash_value = digest.intdigest()
        if node in keys:
            key = keys[node]
            key_type = 'rule' if len(key) == 1 else {'a': 'alternative', 'q': 'quantifier', 'qd': 'quantified'}[key[1]]
            key_name = f'{key_type}:{key[0]}' + (f':{key[2]}' if len(key) > 1 else '')
            result['pool'][key_name].add(hash_value)
            if node in wrappers:
                result['self_embedding'][(key[0], hash_value)] = wrappers[node]
        if isinstance(node, (UnparserRule, UnlexerRule)):
            path[owner] -= 1
        return hash_value, nesting

    _, result['nesting_depth'] = walk(root, root.name, ())
    if codec is not None:
        result['encoded_bytes'] = len(codec.encode_annotated(root, annotations) if isinstance(codec, AnnotatedTreeCodec) else codec.encode(root))
    result['pool'] = {key: sorted(hashes) for key, hashes in result['pool'].items()}
    result['k_paths'] = {size: sorted(paths) for size, paths in result['k_paths'].items()}
    result['quantifiers'] = dict(result['quantifiers'])
    result['lexer_values'] = {key: dict(values) for key, values in result['lexer_values'].items()}
    return result


# Calculate interpolated percentiles for an observed metric.
def _distribution(values):
    if not values:
        return None
    ordered = sorted(values)

    # Interpolate between adjacent observations at the requested percentile.
    def percentile(p):
        index = (len(ordered) - 1) * p
        low = math.floor(index)
        return ordered[low] + (ordered[math.ceil(index)] - ordered[low]) * (index - low)
    return {'min': ordered[0], 'p10': percentile(0.1), 'median': median(ordered), 'p90': percentile(0.9),
            'p95': percentile(0.95), 'max': ordered[-1]}


# Bucket exact depths or powers-of-two token and byte sizes.
def _histogram(values, powers=False):
    counts = Counter()
    for value in values:
        lower = 1 << (value.bit_length() - 1) if powers and value else value
        key = f'{lower}-{2 * lower - 1}' if powers and value else str(value)
        counts[key] += 1
    return dict(sorted(counts.items(), key=lambda item: int(item[0].split('-')[0])))


# Draw a histogram bar scaled to the largest count (non-empty buckets get at least one mark).
def _bar(count, largest, width=40):
    return '#' * max(1, round(width * count / largest)) if count else ''


# Name of the rule that contains an alternation or quantifier. (The
# alternations of token sets, e.g., ~')' in a parser rule, belong to the
# quantifier or alternative that contains them.)
def _owner_name(graph, node):
    while not isinstance(node, RuleNode):
        node = graph.vertices[node.rule_id]
    return node.name


# Read all rule, alternation and quantifier keys from the parser's grammar graph.
def _grammar_inventory(graph):
    rules = sorted({vertex.name for vertex in graph.vertices.values() if isinstance(vertex, RuleNode)})
    alts = defaultdict(lambda: defaultdict(set))
    quants = defaultdict(dict)
    for vertex in graph.vertices.values():
        if isinstance(vertex, AlternationNode):
            alts[_owner_name(graph, vertex)][vertex.idx].update(child.idx for child in vertex.out_neighbours if isinstance(child, AlternativeNode))
        elif isinstance(vertex, QuantifierNode):
            quants[_owner_name(graph, vertex)][vertex.idx] = (vertex.start, vertex.stop)
    return rules, alts, quants


# Enumerate the direct rule references of the parser rules, then the bounded
# two- and three-symbol paths. Lexer rules are leaves in the trees (their
# fragments never appear), so they can only end paths.
def _grammar_paths(graph, limit=1000000):
    neighbours = defaultdict(set)
    for rule in graph.rules:
        if not isinstance(rule, UnparserRuleNode):
            continue
        pending = list(rule.out_neighbours)
        seen = set()
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node)
            if isinstance(node, RuleNode):
                neighbours[rule.name].add(node.name)
            else:
                pending.extend(node.out_neighbours)
    edges = {(source, target) for source, targets in neighbours.items() for target in targets} if sum(map(len, neighbours.values())) <= limit else None
    triples = set()
    for source, middles in neighbours.items():
        for middle in middles:
            for target in neighbours.get(middle, ()):
                triples.add((source, middle, target))
                if len(triples) > limit:
                    return {2: edges, 3: None}
    return {2: edges, 3: triples}


class CorpusStats:
    """
    Corpus statistics merged from the picklable per-file summaries of
    :meth:`ParserTool.parse`. The detailed measurements of the files are merged
    as they arrive, and only their light fields are kept, so that memory does
    not grow with the size of the trees.
    """

    def __init__(self):
        self._files = []
        self._rules = Counter()
        self._alternatives = Counter()
        self._quantifiers = defaultdict(list)
        self._pool = defaultdict(set)
        self._embeddings = {}
        self._nesting = defaultdict(list)
        self._lexer_values = defaultdict(Counter)
        self._lexer_repeats = defaultdict(list)
        self._k_paths = {2: set(), 3: set()}

    # Merge the detailed measurements of a file (if any) and keep its light fields.
    def add(self, item):
        if item['status'] == 'kept' and not item.get('stats_error'):
            self._rules.update(item['rules'])
            self._alternatives.update(item['alternatives'])
            for key, values in item['quantifiers'].items():
                self._quantifiers[key].extend(values)
            for key, hashes in item['pool'].items():
                self._pool[key].update(hashes)
            for key, values in item['self_embedding'].items():
                prior = self._embeddings.setdefault(key, [math.inf, math.inf])
                prior[0], prior[1] = min(prior[0], values[0]), min(prior[1], values[1])
            for key, value in item['self_nesting'].items():
                self._nesting[key].append(value)
            for key, values in item['lexer_values'].items():
                self._lexer_values[key].update(values)
                self._lexer_repeats[key].extend(values.values())
            for size in (2, 3):
                self._k_paths[size].update(tuple(path) for path in item['k_paths'][size])
        self._files.append({key: value for key, value in item.items() if key not in _MERGED_FIELDS})

    # Build the deterministic corpus report and the generator weights.
    def report(self, graph, max_depth=math.inf, max_tokens=math.inf):
        files = sorted(self._files, key=lambda item: item['file'])
        rules, grammar_alts, grammar_quants = _grammar_inventory(graph)
        grammar_paths = _grammar_paths(graph)
        kept = [item for item in files if item['status'] == 'kept']
        detailed = [item for item in kept if not item.get('stats_error')]
        measured = [item for item in files if 'depth' in item]
        counts = Counter(item['status'] for item in files)
        pool_keys = {f'rule:{rule}' for rule in rules}
        pool_keys.update(f'alternative:{rule}:{index}' for rule, alternations in grammar_alts.items() for index in alternations)
        pool_keys.update(f'{kind}:{rule}:{index}' for rule, quantifiers in grammar_quants.items() for index in quantifiers
                         for kind in ('quantifier', 'quantified'))
        alternative_report, alt_weights = {}, {}
        for rule, alternations in sorted(grammar_alts.items()):
            alternative_report[rule], alt_weights[rule] = {}, {}
            for index, alternatives in sorted(alternations.items()):
                observed = {str(alt): self._alternatives[f'{rule}|{index}|{alt}'] for alt in sorted(alternatives)}
                total = sum(observed.values()) + len(observed)
                alternative_report[rule][str(index)] = {'counts': observed, 'never_seen': [alt for alt, count in observed.items() if not count]}
                alt_weights[rule][str(index)] = {alt: (count + 1) / total for alt, count in observed.items()}
        quantifier_report, quant_weights = {}, {}
        for rule, quantifiers in sorted(grammar_quants.items()):
            quantifier_report[rule] = {}
            for index, (start, stop) in sorted(quantifiers.items()):
                values = self._quantifiers[f'{rule}|{index}']
                # The generator decides about one more repetition only between
                # the bounds: every repetition over the minimum is a decision
                # to continue, and every instance below the maximum ended with a
                # decision to stop. Unseen quantifiers keep the default of the
                # generator.
                continues = sum(value - start for value in values)
                stops = sum(value < stop for value in values)
                if continues + stops:
                    quant_weights.setdefault(rule, {})[str(index)] = max(0.01, min(0.95, continues / (continues + stops)))
                quantifier_report[rule][str(index)] = {'count': len(values), 'repetitions': _distribution(values),
                                                       'seen_zero': 0 in values, 'seen_one': 1 in values,
                                                       'seen_two_or_more': any(value >= 2 for value in values),
                                                       'seen_max': stop in values if math.isfinite(stop) else None}
        metrics = {'depth': [item['depth'] for item in measured], 'tokens': [item['tokens'] for item in measured],
                   'nesting_depth': [item['nesting_depth'] for item in detailed], 'nodes': [item['nodes'] for item in detailed],
                   'encoded_bytes': [item['encoded_bytes'] for item in detailed if 'encoded_bytes' in item],
                   'depth_to_nesting_depth': [item['depth'] / item['nesting_depth'] for item in detailed if item['nesting_depth']]}
        # Observed paths missing from the grammar point to a naming mismatch
        # between the trees and the grammar graph (or to hidden tokens).
        k_paths = {}
        for size in (2, 3):
            observed, known = self._k_paths[size], grammar_paths[size]
            covered = observed if known is None else observed & known
            k_paths[str(size)] = {'denominator': len(known) if known is not None else None,
                                  'covered': len(covered), 'covered_paths': [list(path) for path in sorted(covered)],
                                  'never_covered_count': len(known - observed) if known is not None else None,
                                  'never_covered': [list(path) for path in sorted(known - observed)[:1000]] if known is not None else [],
                                  'observed_outside_grammar': len(observed - known) if known is not None else None,
                                  'outside_grammar_examples': [list(path) for path in sorted(observed - known)[:20]] if known is not None else []}
        embedding_report = {}
        for rule in rules:
            rings = [values for (name, _), values in self._embeddings.items() if name == rule]
            embedding_report[rule] = {'different_subtrees': len(rings), 'shortest_ring': min((ring[0] for ring in rings), default=None),
                                      'fewest_wrap_tokens': min((ring[1] for ring in rings), default=None)}
        lexer_report = {}
        for rule in rules:
            vertex = graph.vertices.get((rule,))
            if isinstance(vertex, RuleNode) and vertex.type == 'UnlexerRule':
                repeats = self._lexer_repeats[rule]
                lexer_report[rule] = {'different_values': len(self._lexer_values[rule]),
                                      'top_values': [{'value': value, 'count': count} for value, count in self._lexer_values[rule].most_common(10)],
                                      'average_repeats_per_file': sum(repeats) / len(repeats) if repeats else None}
        deepest = sorted(measured, key=lambda item: (-item['depth'], item['file']))
        most_tokens = sorted(measured, key=lambda item: (-item['tokens'], item['file']))
        report = {'files': files,
                  'counts': {status: counts[status] for status in ('kept', 'too_deep', 'too_many_tokens', 'strict_rejected', 'exception')},
                  'stats_errors': sum(bool(item.get('stats_error')) for item in files),
                  'filtered_by_limits': {'depth': sum(item['over_depth'] for item in files), 'tokens': sum(item['over_tokens'] for item in files),
                                         'both': sum(item['over_depth'] and item['over_tokens'] for item in files)},
                  'deepest': {'file': deepest[0]['file'], 'value': deepest[0]['depth']} if deepest else None,
                  'most_tokens': {'file': most_tokens[0]['file'], 'value': most_tokens[0]['tokens']} if most_tokens else None,
                  'top_depth': [{'file': item['file'], 'value': item['depth']} for item in deepest[:10]],
                  'top_tokens': [{'file': item['file'], 'value': item['tokens']} for item in most_tokens[:10]],
                  'distributions': {name: _distribution(values) for name, values in metrics.items()},
                  'histograms': {name: _histogram(metrics[name], name != 'depth') for name in ('depth', 'tokens', 'encoded_bytes')},
                  'headroom': {'depth': _distribution([max_depth - item['depth'] for item in kept]) if math.isfinite(max_depth) else None,
                               'tokens': _distribution([max_tokens - item['tokens'] for item in kept]) if math.isfinite(max_tokens) else None},
                  'rules': {'counts': {rule: self._rules[rule] for rule in rules}, 'never_seen': [rule for rule in rules if not self._rules[rule]]},
                  'alternatives': {'by_rule': alternative_report,
                                   'never_seen': [f'{rule}|{index}|{alt}' for rule, alternations in alternative_report.items()
                                                  for index, entry in alternations.items() for alt in entry['never_seen']]},
                  'quantifiers': {'by_rule': quantifier_report,
                                  'never_seen': [f'{rule}|{index}' for rule, quantifiers in quantifier_report.items()
                                                 for index, entry in quantifiers.items() if not entry['count']]},
                  'pool_diversity': {'counts': {key: len(self._pool[key]) for key in sorted(pool_keys | self._pool.keys())},
                                     'zero_or_one': sorted(key for key in pool_keys | self._pool.keys() if len(self._pool[key]) <= 1)},
                  'self_embedding': embedding_report,
                  'self_nesting': {rule: {'max': max(values), 'median': median(values)} for rule, values in sorted(self._nesting.items())},
                  'lexer_values': lexer_report,
                  'k_paths': k_paths}
        return report, {'alts': alt_weights, 'quants': quant_weights}


# Write a weights file accepted by grammarinator-generate.
def write_weights(path, weights):
    with open(path, 'w', encoding='utf-8') as output:
        json.dump(weights, output, indent=2, sort_keys=True)
        output.write('\n')


# Log the important totals and bounded, scaled text histograms.
def log_summary(report, logger):
    logger.info('Corpus: %s', ', '.join(f'{status}={count}' for status, count in report['counts'].items()))
    if report['stats_errors']:
        logger.warning('Statistics could not be collected for %d kept trees.', report['stats_errors'])
    logger.info('Filtered: depth=%d, tokens=%d, both=%d', *report['filtered_by_limits'].values())
    logger.info('Deepest: %s; most tokens: %s', report['deepest'], report['most_tokens'])
    logger.info('Rule coverage: %d/%d', sum(bool(count) for count in report['rules']['counts'].values()), len(report['rules']['counts']))
    medians = [report['distributions'][key]['median'] if report['distributions'][key] else None for key in ('depth', 'tokens', 'nesting_depth')]
    logger.info('Median depth=%s, tokens=%s, nesting=%s', *medians)
    for size, coverage in report['k_paths'].items():
        denominator, covered = coverage['denominator'], coverage['covered']
        if denominator is None:
            text = f'{covered} observed; denominator exceeds 1000000'
        elif denominator:
            text = f'{covered}/{denominator} ({covered / denominator:.1%})'
        else:
            text = '0/0 (no grammar paths)'
        logger.info('%s-path coverage: %s', size, text)
        if coverage['observed_outside_grammar']:
            logger.warning('%d observed %s-paths are not in the grammar, e.g., %s.', coverage['observed_outside_grammar'], size,
                           coverage['outside_grammar_examples'][0])
    for metric, histogram in report['histograms'].items():
        logger.info('%s histogram:', metric)
        entries = list(histogram.items())
        step = max(1, math.ceil(len(entries) / 20))
        groups = [entries[offset:offset + step] for offset in range(0, len(entries), step)]
        totals = [sum(value for _, value in group) for group in groups]
        for group, count in zip(groups, totals):
            label = group[0][0] if len(group) == 1 else f'{group[0][0]}..{group[-1][0]}'
            logger.info('  %s: %d %s', label, count, _bar(count, max(totals)))
