# Copyright (c) 2017-2023 Renata Hodovan, Akos Kiss.
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
from os.path import abspath, dirname
from shutil import rmtree

from ..runtime import CooldownModel, DefaultModel, RuleSize, UnparserRule

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
        self._immutable_rules = generator_class._immutable_rules

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
                creators.append(self.mutate)
            if self._enable_recombination:
                creators.append(self.recombine)

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
        limit = self._limit - reserve
        generator = self._generator_factory(limit=limit)

        rule = rule or self._rule or generator._default_rule.__name__
        rule_size = generator._rule_sizes.get(rule, None)

        if not rule_size:
            logger.warning('The size limits of %r are not known.', rule)
        elif rule_size.depth > limit.depth:
            raise ValueError(f'{rule!r} cannot be generated within the given depth: {limit.depth} (min needed: {rule_size.depth}).')
        elif rule_size.tokens > limit.tokens:
            raise ValueError(f'{rule!r} cannot be generated within the given token count: {limit.tokens} (min needed: {rule_size.tokens}).')

        return getattr(generator, rule)()

    def mutate(self):
        """
        Mutate a tree at a random position, i.e., discard and re-generate its
        sub-tree at a randomly selected node.

        :return: The root of the mutated tree.
        :rtype: Rule
        """
        root, annot = self._select_individual()

        options = self._filter_nodes((node for nodes in annot.nodes_by_name.values() for node in nodes), root, annot)
        if options:
            mutated_node = random.choice(options)
            reserve = RuleSize(depth=annot.node_levels[mutated_node],
                               tokens=annot.token_counts[root] - annot.token_counts[mutated_node])
            mutated_node = mutated_node.replace(self.generate(rule=mutated_node.name, reserve=reserve))
            return mutated_node.root

        # If selection strategy fails, we fallback and discard the whole tree
        # and generate a brand new one instead.
        logger.debug('Could not choose node to mutate.')
        return self.generate(rule=root.name)

    def recombine(self):
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
        donor_root, donor_annot = self._select_individual()

        common_types = sorted(set(recipient_annot.nodes_by_name.keys()).intersection(set(donor_annot.nodes_by_name.keys())))
        recipient_options = self._filter_nodes((node for rule_name in common_types for node in recipient_annot.nodes_by_name[rule_name]), recipient_root, recipient_annot)
        # Shuffle suitable nodes with sample.
        for recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            donor_options = donor_annot.nodes_by_name[recipient_node.name]
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth limit.
                if (recipient_annot.node_levels[recipient_node] + donor_annot.node_depths[donor_node] <= self._limit.depth
                        and recipient_annot.token_counts[recipient_root] - recipient_annot.token_counts[recipient_node] + donor_annot.token_counts[donor_node] < self._limit.tokens):
                    recipient_node = recipient_node.replace(donor_node)
                    return recipient_node.root

        # If selection strategy fails, we practically cause the whole donor tree
        # to be the result of recombination.
        logger.debug('Could not find node pairs to recombine.')
        return donor_root

    def _select_individual(self):
        root, annot = self._population.select_individual()
        if not annot:
            annot = Annotations(root)
        return root, annot

    def _add_individual(self, root, path):
        # FIXME: if population cannot store annotations, creating Annotations is
        # superfluous here, but we have no way of knowing that in advance
        self._population.add_individual(root, Annotations(root), path)

    # Filter items from ``nodes`` that can be regenerated within the current
    # maximum depth and token limit (except '<INVALID>' and immutable nodes
    # and nodes without name).
    def _filter_nodes(self, nodes, root, annot):
        return [node for node in nodes
                if node.parent is not None
                and node.name not in self._generator_factory._immutable_rules
                and node.name not in [None, '<INVALID>']
                and annot.node_levels[node] + self._generator_factory._rule_sizes.get(node.name, RuleSize(0, 0)).depth < self._limit.depth
                and annot.token_counts[root] - annot.token_counts[node] + self._generator_factory._rule_sizes.get(node.name, RuleSize(0, 0)).tokens < self._limit.tokens]


class Annotations:

    def __init__(self, root):
        def _annotate(current, level):
            self.node_levels[current] = level

            if current.name not in self.nodes_by_name:
                self.nodes_by_name[current.name] = []
            self.nodes_by_name[current.name].append(current)

            self.node_depths[current] = 0
            self.token_counts[current] = 0
            if isinstance(current, UnparserRule):
                for child in current.children:
                    _annotate(child, level + 1)
                    self.node_depths[current] = max(self.node_depths[current], self.node_depths[child] + 1)
                    self.token_counts[current] += self.token_counts[child] if isinstance(child, UnparserRule) else child.size.tokens + 1

        self.nodes_by_name = {}
        self.node_levels = {}
        self.node_depths = {}
        self.token_counts = {}
        _annotate(root, 0)
