# Copyright (c) 2017-2025 Renata Hodovan, Akos Kiss.
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

from ..runtime import DefaultModel, RuleSize, UnparserRule, WeightedModel

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
                 model_class=None, weights=None,
                 listener_classes=None):
        """
        :param type[~grammarinator.runtime.Generator] generator_class: The class
            of the generator to instantiate.
        :param type[~grammarinator.runtime.Model] model_class: The class of the
            model to instantiate. The model instance is used to instantiate the
            generator.
        :param dict[tuple,float] weights: Initial multipliers of alternatives.
            Used to instantiate a :class:`~grammarinator.runtime.WeightedModel`
            wrapper around the model.
        :param list[type[~grammarinator.runtime.Listener]] listener_classes:
            List of listener classes to instantiate and attach to the generator.
        """
        super().__init__(generator_class)
        self._model_class = model_class or DefaultModel
        self._weights = weights
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
        if self._weights:
            model = WeightedModel(model, weights=self._weights)

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
                 population=None, generate=True, mutate=True, recombine=True, unrestricted=True, keep_trees=False,
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
        :param bool unrestricted: Enable applying possibly grammar-violating creators.
        :param bool keep_trees: Keep generated trees to participate in further mutations or recombinations
               (otherwise, only the initial population will be mutated or recombined). It has effect only if
               population is defined.
        :param list transformers: List of transformers to be applied to postprocess
               the generated tree before serializing it.
        :param serializer: A serializer that takes a tree and produces a string from it (default: :class:`str`).
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

        self._generators = [self.generate]
        self._mutators = [
            self.regenerate_rule,
            self.delete_quantified,
            self.replicate_quantified,
            self.shuffle_quantifieds,
            self.hoist_rule,
            self.swap_local_nodes,
            self.insert_local_node,
        ]
        self._recombiners = [
            self.replace_node,
            self.insert_quantified,
        ]
        if unrestricted:
            self._mutators += [
                self.unrestricted_delete,
                self.unrestricted_hoist_rule,
            ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Delete the output directory if the tests were saved to files and if ``cleanup`` was enabled.
        """
        if self._cleanup and self._out_format and not self._dry_run:
            rmtree(dirname(self._out_format))

    def create_test(self, index):
        """
        Create a new test case with a randomly selected generator method from the
        available options (see :meth:`generate`, :meth:`mutate`, and
        :meth:`recombine`). The generated tree is transformed, serialized and saved
        according to the parameters used to initialize the current tool object.

        :param int index: Index of the test case to be generated.
        :return: Path to the generated serialized test file. It may be empty if
            the tool object was initialized with an empty ``out_format`` or
            ``None`` if ``dry_run`` was enabled, and hence the test file was not
            saved.
        :rtype: str
        """
        root = self.create()
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

    def _select_creator(self, creators, individual1, individual2):  # pylint: disable=unused-argument
        # NOTE: May be overridden.
        return random.choice(creators)

    def _create_tree(self, creators, individual1, individual2):
        creator = self._select_creator(creators, individual1, individual2)
        root = creator(individual1, individual2)
        for transformer in self._transformers:
            root = transformer(root)
        return root

    def create(self):
        """
        Create a new tree with a randomly selected generator method from the
        available options (see :meth:`generate`, :meth:`mutate`, and
        :meth:`recombine`). The generated tree is also transformed according to the
        parameters used to initialize the current tool object.

        :return: The root of the created tree.
        :rtype: Rule
        """
        individual1, individual2 = (self._ensure_individuals(None, None)) if self._population else (None, None)
        creators = []
        if self._enable_generation:
            creators.extend(self._generators)
        if self._population:
            if self._enable_mutation:
                creators.extend(self._mutators)
            if self._enable_recombination:
                creators.extend(self._recombiners)
        return self._create_tree(creators, individual1, individual2)

    def mutate(self, individual=None):
        """
        Dispatcher method for mutation operators: it picks one operator randomly and
        creates a new tree by applying the operator to an individual. The generated
        tree is also transformed according to the parameters used to initialize the
        current tool object.

        Supported mutation operators: :meth:`regenerate_rule`,
        :meth:`delete_quantified`, :meth:`replicate_quantified`,
        :meth:`shuffle_quantifieds`, :meth:`hoist_rule`,
        :meth:`unrestricted_delete`, :meth:`unrestricted_hoist_rule`,
        :meth:`swap_local_nodes`, :meth:`insert_local_node`

        :param ~grammarinator.runtime.Individual individual: The population item to
            be mutated.
        :return: The root of the mutated tree.
        :rtype: Rule
        """
        # NOTE: Intentionally does not check self._enable_mutation!
        # If you call this explicitly, then so be it, even if mutation is disabled.
        # If individual is None, population MUST exist.
        individual = self._ensure_individual(individual)
        return self._create_tree(self._mutators, individual, None)

    def recombine(self, individual1=None, individual2=None):
        """
        Dispatcher method for recombination operators: it picks one operator
        randomly and creates a new tree by applying the operator to an individual.
        The generated tree is also transformed according to the parameters used to
        initialize the current tool object.

        Supported recombination operators: :meth:`replace_node`,
        :meth:`insert_quantified`

        :param ~grammarinator.runtime.Individual individual1: The population item to
            be used as a recipient during crossover.
        :param ~grammarinator.runtime.Individual individual2: The population item to
            be used as a donor during crossover.
        :return: The root of the recombined tree.
        :rtype: Rule
        """
        # NOTE: Intentionally does not check self._enable_recombination!
        # If you call this explicitly, then so be it, even if recombination is disabled.
        # If any of the individuals is None, population MUST exist.
        individual1, individual2 = self._ensure_individuals(individual1, individual2)
        return self._create_tree(self._recombiners, individual1, individual2)

    def generate(self, _individual1=None, _individual2=None, *, rule=None, reserve=None):
        """
        Instantiate a new generator and generate a new tree from scratch.

        :param str rule: Name of the rule to start generation from.
        :param RuleSize reserve: Size budget that needs to be put in reserve
            before generating the tree. Practically, deduced from the initially
            specified limit. (default values: 0, 0)
        :return: The root of the generated tree.
        :rtype: Rule
        """
        # NOTE: Intentionally does not check self._enable_generation!
        # If you call this explicitly, then so be it, even if generation is disabled.
        reserve = reserve if reserve is not None else RuleSize()
        generator = self._generator_factory(limit=self._limit - reserve)
        rule = rule or self._rule or generator._default_rule.__name__
        return getattr(generator, rule)()

    def _ensure_individual(self, individual):
        return individual or self._population.select_individual()

    def _ensure_individuals(self, individual1, individual2):
        individual1 = self._ensure_individual(individual1)
        individual2 = individual2 or self._population.select_individual()
        return individual1, individual2

    def regenerate_rule(self, individual=None, _=None):
        """
        Mutate a tree at a random position, i.e., discard and re-generate its
        sub-tree at a randomly selected node.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the mutated tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations

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

    def replace_node(self, recipient_individual=None, donor_individual=None):
        """
        Recombine two trees at random positions where the nodes are compatible
        with each other (i.e., they share the same node name). One of the trees
        is called the recipient while the other is the donor. The sub-tree
        rooted at a random node of the recipient is discarded and replaced
        by the sub-tree rooted at a random node of the donor.

        :param ~grammarinator.runtime.Individual recipient_individual:
            The population item to be used as a recipient during crossover.
        :param ~grammarinator.runtime.Individual donor_individual:
            The population item to be used as a donor during crossover.
        :return: The root of the recombined tree.
        :rtype: Rule
        """
        recipient_individual, donor_individual = self._ensure_individuals(recipient_individual, donor_individual)
        recipient_root, recipient_annot = recipient_individual.root, recipient_individual.annotations
        donor_annot = donor_individual.annotations

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

    def insert_quantified(self, recipient_individual=None, donor_individual=None):
        """
        Selects two compatible quantifier nodes from two trees randomly and if
        the quantifier node of the recipient tree is not full (the number of
        its children is less than the maximum count), then add one new child
        to it at a random position from the children of donors quantifier node.

        :param ~grammarinator.runtime.Individual recipient_individual:
            The population item to be used as a recipient during crossover.
        :param ~grammarinator.runtime.Individual donor_individual:
            The population item to be used as a donor during crossover.
        :return: The root of the extended tree.
        :rtype: Rule
        """
        recipient_individual, donor_individual = self._ensure_individuals(recipient_individual, donor_individual)
        recipient_root, recipient_annot = recipient_individual.root, recipient_individual.annotations
        donor_annot = donor_individual.annotations

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

    def delete_quantified(self, individual=None, _=None):
        """
        Removes an optional subtree randomly from a quantifier node.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the modified tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [child for node in annot.quants if len(node.children) > node.start for child in node.children]
        if options:
            removed_node = random.choice(options)
            removed_node.remove()

        # Return with the original root, whether the deletion was successful or not.
        return root

    def unrestricted_delete(self, individual=None, _=None):
        """
        Remove a subtree rooted in any kind of rule node randomly without any
        further restriction.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the modified tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [node for node in annot.rules if node != root]
        if options:
            removed_node = random.choice(options)
            removed_node.remove()

        # Return with the original root, whether the deletion was successful or not.
        return root

    def replicate_quantified(self, individual=None, _=None):
        """
        Select a quantified sub-tree randomly, replicate it and insert it again if
        the maximum quantification count is not reached yet.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the modified tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        root_options = [node for node in annot.quants if node.stop > len(node.children)]
        recipient_root_token_counts = annot.token_counts[root]
        node_options = [child for root in root_options for child in root.children if
                        recipient_root_token_counts < recipient_root_token_counts + annot.token_counts[child] <= self._limit.tokens]
        if node_options:
            node_to_repeat = random.choice(node_options)
            max_repeat = (self._limit.tokens - recipient_root_token_counts) // annot.token_counts[node_to_repeat]
            for _ in range(random.randint(1, max_repeat)):
                node_to_repeat.parent.insert_child(idx=random.randint(0, len(node_to_repeat.parent.children)), node=deepcopy(node_to_repeat))

        # Return with the original root, whether the replication was successful or not.
        return root

    def shuffle_quantifieds(self, individual=None, _=None):
        """
        Select a quantifier node and shuffle its quantified sub-trees.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the modified tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [node for node in annot.quants if len(node.children) > 1]
        if options:
            node_to_shuffle = random.choice(options)
            random.shuffle(node_to_shuffle.children)

        # Return with the original root, whether the shuffling was successful or not.
        return root

    def hoist_rule(self, individual=None, _=None):
        """
        Select an individual of the population to be mutated and select two
        rule nodes from it which share the same rule name and are in
        ancestor-descendant relationship making possible for the descendant
        to replace its ancestor.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the hoisted tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        for rule in random.sample(annot.rules, k=len(annot.rules)):
            parent = rule.parent
            while parent:
                if parent.name == rule.name:
                    parent.replace(rule)
                    return root
                parent = parent.parent
        return root

    def unrestricted_hoist_rule(self, individual=None, _=None):
        """
        Select two rule nodes from the input individual which are in
        ancestor-descendant relationship (without type compatibility check) and
        replace the ancestor with the selected descendant.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated.
        :return: The root of the modified tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        for rule in random.sample(annot.rules, k=len(annot.rules)):
            options = []
            parent = rule.parent
            while parent and parent != root:
                if isinstance(parent, UnparserRule) and len(parent.children) > 1 and not rule.equalTokens(parent):
                    options.append(parent)
                parent = parent.parent

            if options:
                random.choice(options).replace(rule)
                return root
        return root

    def swap_local_nodes(self, individual=None, _=None):
        """
        Swap two non-overlapping subtrees at random positions in a single test
        where the nodes are compatible with each other (i.e., they share the same node name).

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated
        :return: The root of the mutated tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations

        options = dict(annot.rules_by_name)
        options.update(annot.quants_by_name)
        options.update(annot.alts_by_name)

        for _, nodes in random.sample(list(options.items()), k=len(options)):
            # Skip node types without two instances.
            if len(nodes) < 2:
                continue

            shuffled = random.sample(nodes, k=len(nodes))
            for i, first_node in enumerate(shuffled[:-1]):
                first_node_level = annot.node_levels[first_node]
                first_node_depth = annot.node_depths[first_node]
                for second_node in shuffled[i + 1:]:
                    second_node_level = annot.node_levels[second_node]
                    second_node_depth = annot.node_depths[second_node]
                    if (first_node_level + second_node_depth > self._limit.depth
                            and second_node_level + first_node_depth > self._limit.depth):
                        continue

                    # Avoid swapping two identical nodes with each other.
                    if first_node.equalTokens(second_node):
                        continue

                    # Ensure the subtrees rooted at recipient and donor nodes are disjunct.
                    upper_node, lower_node = (first_node, second_node) if first_node_level < second_node_level else (second_node, first_node)
                    disjunct = True
                    parent = lower_node.parent
                    while parent and disjunct:
                        disjunct = parent != upper_node
                        parent = parent.parent

                    if not disjunct:
                        continue

                    first_parent = first_node.parent
                    second_parent = second_node.parent
                    first_parent.children[first_parent.children.index(first_node)] = second_node
                    second_parent.children[second_parent.children.index(second_node)] = first_node
                    first_node.parent = second_parent
                    second_node.parent = first_parent
                    return root
        return root

    def insert_local_node(self, individual=None, _=None):
        """
        Select two compatible quantifier nodes from a single test and
        insert a random quantified subtree of the second one into the
        first one at a random position, while the quantifier restrictions
        are ensured.

        :param ~grammarinator.runtime.Individual individual: The population item to be mutated
        :return: The root of the mutated tree.
        :rtype: Rule
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [quantifiers for quantifiers in annot.quants_by_name.values() if len(quantifiers) > 1]
        if not options:
            return root

        root_token_counts = annot.token_counts[root]
        for quantifiers in random.sample(options, k=len(options)):
            shuffled = random.sample(quantifiers, k=len(quantifiers))
            for i, recipient_node in enumerate(shuffled[:-1]):
                if len(recipient_node.children) >= recipient_node.stop:
                    continue

                recipient_node_level = annot.node_levels[recipient_node]
                for donor_quantifier in shuffled[i + 1:]:
                    for donor_quantified_node in donor_quantifier.children:
                        if (recipient_node_level + annot.node_depths[donor_quantified_node] <= self._limit.depth
                                and root_token_counts + annot.token_counts[donor_quantified_node] <= self._limit.tokens):
                            recipient_node.insert_child(random.randint(0, len(recipient_node.children)) if recipient_node.children else 0,
                                                        deepcopy(donor_quantified_node))
                            return root
        return root
