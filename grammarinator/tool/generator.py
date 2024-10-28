# Copyright (c) 2017-2024 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import logging
import os
import random

from contextlib import nullcontext
from copy import deepcopy
from os.path import abspath, dirname
from shutil import rmtree

from ..runtime import CooldownModel, DefaultModel, ParentRule, RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantifier

logger = logging.getLogger(__name__)


class GeneratorFactory:
    """
    Base class of generator factories. A generator factory is a generalization
    of a generator class. It has to be a callable that, when called, must return
    a generator instance. It must also expose some properties of the generator
    class it generalizes that are required to guide generation or mutation by
    :class:`GeneratorTool`.

    This factory generalizes a generator class by simply wrapping it and
    forwarding call operations to instantiations of the wrapped class.
    Furthermore, generator factories deriving from this base class are
    guaranteed to expose all the required generator class properties.
    """

    def __init__(self, generator_class):
        """
        :param type[~grammarinator.runtime.Generator] generator_class: The class
            of the wrapped generator.

        :ivar type[~grammarinator.runtime.Generator] _generator_class: The class
            of the wrapped generator.
        """
        self._generator_class = generator_class
        # Exposing some class variables of the encapsulated generator.
        # In the generator class, they start with `_` to avoid any kind of
        # collision with rule names, so they start with `_` here as well.
        self._immutable_rules = generator_class._immutable_rules
        self._rule_sizes = generator_class._rule_sizes
        self._alt_sizes = generator_class._alt_sizes
        self._quant_sizes = generator_class._quant_sizes

    def __call__(self, limit=None):
        """
        Create a new generator instance.

        :param RuleSize limit: The limit on the depth of the trees and on the
            number of tokens (number of unlexer rule calls), i.e., it must be
            possible to finish generation from the selected node so that the
            overall depth and token count of the tree does not exceed these
            limits (default: :class:`~grammarinator.runtime.RuleSize`. ``max``).
            Used to instantiate the generator.
        :return: The created generator instance.
        :rtype: ~grammarinator.runtime.Generator
        """
        return self._generator_class(limit=limit)


class DefaultGeneratorFactory(GeneratorFactory):
    """
    The default generator factory implementation. When called, a new generator
    instance is created backed by a new decision model instance and a set of
    newly created listener objects is attached.
    """

    def __init__(self, generator_class, *,
                 model_class=None, cooldown=1.0, weights=None, lock=None,
                 listener_classes=None):
        """
        :param type[~grammarinator.runtime.Generator] generator_class: The class
            of the generator to instantiate.
        :param type[~grammarinator.runtime.Model] model_class: The class of the
            model to instantiate. The model instance is used to instantiate the
            generator.
        :param float cooldown: Cooldown factor. Used to instantiate a
            :class:`~grammarinator.runtime.CooldownModel` wrapper around the
            model.
        :param dict[tuple,float] weights: Initial multipliers of alternatives.
            Used to instantiate a :class:`~grammarinator.runtime.CooldownModel`
            wrapper around the model.
        :param multiprocessing.Lock lock: Lock object when generating in
            parallel. Used to instantiate a
            :class:`~grammarinator.runtime.CooldownModel` wrapper around the
            model.
        :param list[type[~grammarinator.runtime.Listener]] listener_classes:
            List of listener classes to instantiate and attach to the generator.
        """
        super().__init__(generator_class)
        self._model_class = model_class or DefaultModel
        self._cooldown = cooldown
        self._weights = weights
        self._lock = lock
        self._listener_classes = listener_classes or []

    def __call__(self, limit=None):
        """
        Create a new generator instance according to the settings specified for
        the factory instance and for this method.

        :param RuleSize limit: The limit on the depth of the trees and on the
            number of tokens (number of unlexer rule calls), i.e., it must be
            possible to finish generation from the selected node so that the
            overall depth and token count of the tree does not exceed these
            limits (default: :class:`~grammarinator.runtime.RuleSize`. ``max``).
            Used to instantiate the generator.
        :return: The created generator instance.
        :rtype: ~grammarinator.runtime.Generator
        """
        model = self._model_class()
        if self._cooldown < 1 or self._weights:
            model = CooldownModel(model, cooldown=self._cooldown, weights=self._weights, lock=self._lock)

        listeners = []
        for listener_class in self._listener_classes:
            listeners.append(listener_class())

        generator = self._generator_class(model=model, listeners=listeners, limit=limit)

        return generator


class GeneratorTool:
    """
    Tool to create new test cases using the generator produced by ``grammarinator-process``.
    """

    def __init__(self, generator_factory, out_format, lock=None, rule=None, limit=None,
                 population=None, generate=True, mutate=True, recombine=True, keep_trees=False,
                 transformers=None, serializer=None,
                 cleanup=True, encoding='utf-8', errors='strict', dry_run=False):
        """
        :param type[~grammarinator.runtime.Generator] or GeneratorFactory generator_factory:
            A callable that can produce instances of a generator. It is a
            generalization of a generator class: it has to instantiate a
            generator object, and it may also set the decision model and the
            listeners of the generator as well. It also has to expose some
            properties of the generator class necessary to guide generation or
            mutation. In the simplest case, it can be a
            ``grammarinator-process``-created subclass of
            :class:`~grammarinator.runtime.Generator`, but in more complex
            scenarios a factory can be used, e.g., an instance of a subclass of
            :class:`GeneratorFactory`, like :class:`DefaultGeneratorFactory`.
        :param str rule: Name of the rule to start generation from (default: the
            default rule of the generator).
        :param str out_format: Test output description. It can be a file path pattern possibly including the ``%d``
               placeholder which will be replaced by the index of the test case. Otherwise, it can be an empty string,
               which will result in printing the test case to the stdout (i.e., not saving to file system).
        :param multiprocessing.Lock lock: Lock object necessary when printing test cases in parallel (optional).
        :param RuleSize limit: The limit on the depth of the trees and on the
            number of tokens (number of unlexer rule calls), i.e., it must be
            possible to finish generation from the selected node so that the
            overall depth and token count of the tree does not exceed these
            limits (default: :class:`~grammarinator.runtime.RuleSize`. ``max``).
        :param ~grammarinator.runtime.Population population: Tree pool for
            mutation and recombination, e.g., an instance of
            :class:`DefaultPopulation`.
        :param bool generate: Enable generating new test cases from scratch, i.e., purely based on grammar.
        :param bool mutate: Enable mutating existing test cases, i.e., re-generate part of an existing test case based on grammar.
        :param bool recombine: Enable recombining existing test cases, i.e., replace part of a test case with a compatible part from another test case.
        :param bool keep_trees: Keep generated trees to participate in further mutations or recombinations
               (otherwise, only the initial population will be mutated or recombined). It has effect only if
               population is defined.
        :param list transformers: List of transformers to be applied to postprocess
               the generated tree before serializing it.
        :param serializer: A seralizer that takes a tree and produces a string from it (default: :class:`str`).
               See :func:`grammarinator.runtime.simple_space_serializer` for a simple solution that concatenates tokens with spaces.
        :param bool cleanup: Enable deleting the generated tests at :meth:`__exit__`.
        :param str encoding: Output file encoding.
        :param str errors: Encoding error handling scheme.
        :param bool dry_run: Enable or disable the saving or printing of the result of generation.
        """

        self._generator_factory = generator_factory
        self._transformers = transformers or []
        self._serializer = serializer or str
        self._rule = rule

        if out_format and not dry_run:
            os.makedirs(abspath(dirname(out_format)), exist_ok=True)

        self._out_format = out_format
        self._lock = lock or nullcontext()
        self._limit = limit or RuleSize.max
        self._population = population
        self._enable_generation = generate
        self._enable_mutation = mutate
        self._enable_recombination = recombine
        self._keep_trees = keep_trees
        self._cleanup = cleanup
        self._encoding = encoding
        self._errors = errors
        self._dry_run = dry_run

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Delete the output directory if the tests were saved to files and if ``cleanup`` was enabled.
        """
        if self._cleanup and self._out_format and not self._dry_run:
            rmtree(dirname(self._out_format))

    def create(self, index):
        """
        Create new test case with a randomly selected generator method from the available
        options (i.e., via :meth:`generate`, :meth:`mutate`, or :meth:`recombine`). The
        generated tree is transformed, serialized and saved according to the parameters
        used to initialize the current tool object.

        :param int index: Index of the test case to be generated.
        :return: Path to the generated serialized test file. It may be empty if
            the tool object was initialized with an empty ``out_format`` or
            ``None`` if ``dry_run`` was enabled, and hence the test file was not
            saved.
        :rtype: str
        """
        creators = []
        if self._enable_generation:
            creators.append(self.generate)
        if self._population:
            if self._enable_mutation:
                creators.extend((self.regenerate_rule, self.delete_quantified, self.replicate_quantified, self.shuffle_quantifieds, self.hoist_rule))
            if self._enable_recombination:
                creators.extend((self.replace_node, self.insert_quantified))

        creator = random.choice(creators)
        root = creator()

        for transformer in self._transformers:
            root = transformer(root)

        test = self._serializer(root)
        if self._dry_run:
            return None

        test_fn = self._out_format % index if '%d' in self._out_format else self._out_format

        if self._population is not None and self._keep_trees:
            self._population.add_individual(root, path=test_fn)

        if test_fn:
            with codecs.open(test_fn, 'w', self._encoding, self._errors) as f:
                f.write(test)
        else:
            with self._lock:
                print(test)

        return test_fn

    def generate(self, *, rule=None, reserve=None):
        """
        Instantiate a new generator and generate a new tree from scratch.

        :param str rule: Name of the rule to start generation from.
        :param RuleSize reserve: Size budget that needs to be put in reserve
            before generating the tree. Practically, deduced from the initially
            specified limit. (default values: 0, 0)
        :return: The root of the generated tree.
        :rtype: Rule
        """
        reserve = reserve if reserve is not None else RuleSize()
        generator = self._generator_factory(limit=self._limit - reserve)
        rule = rule or self._rule or generator._default_rule.__name__
        return getattr(generator, rule)()

    def mutate(self):
        """
        Dispatcher method for mutation operators: it picks one operator
        randomly and creates a new tree with it.

        Supported mutation operators: :meth:`regenerate_rule`, :meth:`delete_quantified`, :meth:`replicate_quantified`, :meth:`shuffle_quantifieds`, :meth:`hoist_rule`

        :return: The root of the mutated tree.
        :rtype: Rule
        """
        return random.choice((self.regenerate_rule, self.delete_quantified, self.replicate_quantified, self.shuffle_quantifieds, self.hoist_rule))()

    def recombine(self):
        """
        Dispatcher method for recombination operators: it picks one operator
        randomly and creates a new tree with it.

        Supported recombination operators: :meth:`replace_node`, :meth:`insert_quantified`

        :return: The root of the recombined tree.
        :rtype: Rule
        """
        return random.choice((self.replace_node, self.insert_quantified))()

    def regenerate_rule(self):
        """
        Mutate a tree at a random position, i.e., discard and re-generate its
        sub-tree at a randomly selected node.

        :return: The root of the mutated tree.
        :rtype: Rule
        """
        root, annot = self._select_individual()

        # Filter items from the nodes of the selected tree that can be regenerated
        # within the current maximum depth and token limit (except immutable nodes).
        root_token_counts = annot.token_counts[root]
        options = [node for nodes in annot.rules_by_name.values() for node in nodes
                   if (node.parent is not None
                       and annot.node_levels[node] + self._generator_factory._rule_sizes.get(node.name, RuleSize(0, 0)).depth < self._limit.depth
                       and root_token_counts - annot.token_counts[node] + self._generator_factory._rule_sizes.get(node.name, RuleSize(0, 0)).tokens < self._limit.tokens)]
        if options:
            mutated_node = random.choice(options)
            reserve = RuleSize(depth=annot.node_levels[mutated_node],
                               tokens=root_token_counts - annot.token_counts[mutated_node])
            mutated_node = mutated_node.replace(self.generate(rule=mutated_node.name, reserve=reserve))
            return mutated_node.root

        # If selection strategy fails, we fallback and discard the whole tree
        # and generate a brand new one instead.
        return self.generate(rule=root.name)

    def replace_node(self):
        """
        Recombine two trees at random positions where the nodes are compatible
        with each other (i.e., they share the same node name). One of the trees
        is called the recipient while the other is the donor. The sub-tree
        rooted at a random node of the recipient is discarded and replaced
        by the sub-tree rooted at a random node of the donor.

        :return: The root of the recombined tree.
        :rtype: Rule
        """
        recipient_root, recipient_annot = self._select_individual()
        _, donor_annot = self._select_individual()

        recipient_lookup = dict(recipient_annot.rules_by_name)
        recipient_lookup.update(recipient_annot.quants_by_name)
        recipient_lookup.update(recipient_annot.alts_by_name)

        donor_lookup = dict(donor_annot.rules_by_name)
        donor_lookup.update(donor_annot.quants_by_name)
        donor_lookup.update(donor_annot.alts_by_name)
        common_types = sorted(set(recipient_lookup.keys()) & set(donor_lookup.keys()))

        recipient_options = [(rule_name, node) for rule_name in common_types for node in recipient_lookup[rule_name] if node.parent]
        recipient_root_token_counts = recipient_annot.token_counts[recipient_root]
        # Shuffle suitable nodes with sample.
        for rule_name, recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            donor_options = donor_lookup[rule_name]
            recipient_node_level = recipient_annot.node_levels[recipient_node]
            recipient_node_tokens = recipient_annot.token_counts[recipient_node]
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth limit.
                if (recipient_node_level + donor_annot.node_depths[donor_node] <= self._limit.depth
                        and recipient_root_token_counts - recipient_node_tokens + donor_annot.token_counts[donor_node] < self._limit.tokens):
                    recipient_node.replace(donor_node)
                    return recipient_root

        # If selection strategy fails, we practically cause the whole recipient tree
        # to be the result of recombination.
        return recipient_root

    def insert_quantified(self):
        """
        Selects two compatible quantifier nodes from two trees randomly and if
        the quantifier node of the recipient tree is not full (the number of
        its children is less than the maximum count), then add one new child
        to it at a random position from the children of donors quantifier node.

        :return: The root of the extended tree.
        :rtype: Rule
        """
        recipient_root, recipient_annot = self._select_individual()
        _, donor_annot = self._select_individual()

        common_types = sorted(set(recipient_annot.quants_by_name.keys()) & set(donor_annot.quants_by_name.keys()))
        recipient_options = [(name, node) for name in common_types for node in recipient_annot.quants_by_name[name] if len(node.children) < node.stop]
        recipient_root_token_counts = recipient_annot.token_counts[recipient_root]
        for rule_name, recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            recipient_node_level = recipient_annot.node_levels[recipient_node]
            donor_options = [quantified for quantifier in donor_annot.quants_by_name[rule_name] for quantified in quantifier.children]
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth and token limits.
                if (recipient_node_level + donor_annot.node_depths[donor_node] <= self._limit.depth
                        and recipient_root_token_counts + donor_annot.token_counts[donor_node] < self._limit.tokens):
                    recipient_node.insert_child(random.randint(0, len(recipient_node.children)), donor_node)
                    return recipient_root

        # If selection strategy fails, we practically cause the whole recipient tree
        # to be the result of insertion.
        return recipient_root

    def delete_quantified(self):
        """
        Removes an optional subtree randomly from a quantifier node.

        :return: The root of the modified tree.
        :rtype: Rule
        """
        root, annot = self._select_individual()
        options = [child for node in annot.quants if len(node.children) > node.start for child in node.children]
        if options:
            removed_node = random.choice(options)
            removed_node.remove()

        # Return with the original root, whether the deletion was successful or not.
        return root

    def replicate_quantified(self):
        """
        Select a quantified sub-tree randomly, replicate it and insert it again if
        the maximum quantification count is not reached yet.

        :return: The root of the modified tree.
        :rtype: Rule
        """
        root, annot = self._select_individual()
        root_options = [node for node in annot.quants if node.stop > len(node.children)]
        recipient_root_token_counts = annot.token_counts[root]
        node_options = [child for root in root_options for child in root.children if
                        recipient_root_token_counts + annot.token_counts[child] <= self._limit.tokens]
        if node_options:
            node_to_repeat = random.choice(node_options)
            node_to_repeat.parent.insert_child(idx=random.randint(0, len(node_to_repeat.parent.children)), node=deepcopy(node_to_repeat))

        # Return with the original root, whether the replication was successful or not.
        return root

    def shuffle_quantifieds(self):
        """
        Select a quantifier node and shuffle its quantified sub-trees.

        :return: The root of the modified tree.
        :rtype: Rule
        """
        root, annot = self._select_individual()
        options = [node for node in annot.quants if len(node.children) > 1]
        if options:
            node_to_shuffle = random.choice(options)
            random.shuffle(node_to_shuffle.children)

        # Return with the original root, whether the shuffling was successful or not.
        return root

    def hoist_rule(self):
        """
        Select an individual of the population to be mutated and select two
        rule nodes from it which share the same rule name and are in
        ancestor-descendant relationship making possible for the descendant
        to replace its ancestor.

        :return: The root of the hoisted tree.
        :rtype: Rule
        """
        root, annot = self._select_individual()
        for rule in random.sample(annot.rules, k=len(annot.rules)):
            parent = rule.parent
            while parent:
                if parent.name == rule.name:
                    parent.replace(rule)
                    return root
                parent = parent.parent
        return root

    def _select_individual(self):
        root, annot = self._population.select_individual()
        if not annot:
            annot = Annotations(root, self._generator_factory._immutable_rules)
        return root, annot

    def _add_individual(self, root, path):
        # FIXME: if population cannot store annotations, creating Annotations is
        # superfluous here, but we have no way of knowing that in advance
        self._population.add_individual(root, Annotations(root, self._generator_factory._immutable_rules), path)


class Annotations:

    def __init__(self, root, immutable_rules):
        def _annotate(current, level):
            nonlocal current_rule_name
            self.node_levels[current] = level

            if isinstance(current, (UnlexerRule, UnparserRule)):
                if current.name and current.name != '<INVALID>':
                    current_rule_name = (current.name,)
                    if current_rule_name not in immutable_rules:
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
        return [rule for rules in self.rules_by_name.values() for rule in rules]

    @property
    def alts(self):
        return [alt for alts in self.alts_by_name.values() for alt in alts]

    @property
    def quants(self):
        return [quant for quants in self.quants_by_name.values() for quant in quants]
