# Copyright (c) 2023-2025 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .rule import ParentRule, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantifier


class Population:
    """
    Abstract base class of populations that store test cases in tree form (i.e.,
    individuals) and can select trees for mutation or recombination based on some strategy.
    """

    def empty(self):
        """
        Return whether the population is empty.

        Raises :exc:`NotImplementedError` by default.

        :return: ``True`` if the population is empty and ``False`` otherwise.
        :rtype: bool
        """
        raise NotImplementedError()

    def __bool__(self):
        """
        Truth value testing of Populations.

        :return: ``True`` if the population is not empty and ``False`` otherwise.
        :rtype: bool
        """
        return not self.empty()

    def add_individual(self, root, path=None):
        """
        Add a tree to the population.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule root: Root of the tree to be added.
        :param str path: The pathname of the test case corresponding to the
            tree, if it exists. May be used for debugging.
        """
        raise NotImplementedError()

    def select_individual(self):
        """
        Select an individual of the population.

        Raises :exc:`NotImplementedError` by default.

        :return: A single individual of the population.
        :rtype: Individual
        """
        raise NotImplementedError()


class Individual:
    """
    Abstract base class of population individuals.
    """
    def __init__(self, name):
        """
        :param str name: Name or identifier of the individual.
        """
        self.name = name
        self._annot = None

    @property
    def root(self):
        """
        Return the root node of the tree of the individual.

        :return: Root of the tree.
        :rtype: ~grammarinator.runtime.Rule
        """
        raise NotImplementedError()

    @property
    def annotations(self):
        """
        Return the associated annotations if available, otherwise compute them immediately.

        :return: The annotations associated with the tree.
        :rtype: Annotations
        """
        if not self._annot:
            self._annot = Annotations(self.root)
        return self._annot


class Annotations:
    """
    Class for calculating and managing additional metadata needed by the
    mutators, particularly to enforce size constraints and facilitate node
    filtering by rule types.
    """

    def __init__(self, root):
        """
        :param ~grammarinator.runtime.Rule root: Root of the tree to be annotated.
        """
        def _annotate(current, level):
            nonlocal current_rule_name
            self.node_levels[current] = level

            if isinstance(current, (UnlexerRule, UnparserRule)):
                if current.name and current.name != '<INVALID>':
                    current_rule_name = (current.name,)
                    if not isinstance(current, UnlexerRule) or not current.immutable:
                        if current_rule_name not in self.rules_by_name:
                            self.rules_by_name[current_rule_name] = []
                        self.rules_by_name[current_rule_name].append(current)
                else:
                    current_rule_name = None
            elif current_rule_name:
                if isinstance(current, UnparserRuleQuantifier):
                    node_name = current_rule_name + ('q', current.idx,)
                    if node_name not in self.quants_by_name:
                        self.quants_by_name[node_name] = []
                    self.quants_by_name[node_name].append(current)
                elif isinstance(current, UnparserRuleAlternative):
                    node_name = current_rule_name + ('a', current.alt_idx,)
                    if node_name not in self.alts_by_name:
                        self.alts_by_name[node_name] = []
                    self.alts_by_name[node_name].append(current)

            self.node_depths[current] = 0
            self.token_counts[current] = 0
            if isinstance(current, ParentRule):
                for child in current.children:
                    _annotate(child, level + 1)
                    self.node_depths[current] = max(self.node_depths[current], self.node_depths[child] + 1)
                    self.token_counts[current] += self.token_counts[child] if isinstance(child, ParentRule) else child.size.tokens + 1

        current_rule_name = None
        self.rules_by_name = {}
        self.alts_by_name = {}
        self.quants_by_name = {}
        self.node_levels = {}
        self.node_depths = {}
        self.token_counts = {}
        _annotate(root, 0)

    @property
    def rules(self):
        """
        Get nodes created from rule nodes.

        :return: List of rule nodes.
        :rtype: list[~grammarinator.runtime.Rule]
        """
        return [rule for rules in self.rules_by_name.values() for rule in rules]

    @property
    def alts(self):
        """
        Get nodes created from alternatives.

        :return: List of alternative nodes.
        :rtype: list[UnparserRuleAlternative]
        """
        return [alt for alts in self.alts_by_name.values() for alt in alts]

    @property
    def quants(self):
        """
        Get nodes created from quantified expressions.

        :return: List of quantifier nodes.
        :rtype: list[UnparserRuleQuantifier]
        """
        return [quant for quants in self.quants_by_name.values() for quant in quants]
