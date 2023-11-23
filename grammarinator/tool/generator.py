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

from ..runtime import CooldownModel, DefaultModel, RuleSize

logger = logging.getLogger(__name__)


class DefaultGeneratorFactory:
    """
    The default generator factory implementation. Instances of
    ``DefaultGeneratorFactory`` are callable. When called, a new generator
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
        self._generator_class = generator_class
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
        :param generator_factory: A callable that can produce instances of a
            generator. It is a generalization of a generator class: it has to
            instantiate a generator object, and it may also set the decision
            model and the listeners of the generator as well. In the simplest
            case, it can be a ``grammarinator-process``-created subclass of
            :class:`~grammarinator.runtime.Generator`, but in more complex
            scenarios a factory can be used, e.g., an instance of
            :class:`DefaultGeneratorFactory`.
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
            if self._enable_mutation and self._population.can_mutate():
                creators.append(self.mutate)
            if self._enable_recombination and self._population.can_recombine():
                creators.append(self.recombine)
        creator = random.choice(creators)

        if creator == self.generate:
            root = creator()
        elif creator == self.mutate:
            mutated_node, reserve = self._population.select_to_mutate(self._limit)
            root = creator(mutated_node, reserve)
        elif creator == self.recombine:
            recipient_node, donor_node = self._population.select_to_recombine(self._limit)
            root = creator(recipient_node, donor_node)

        for transformer in self._transformers:
            root = transformer(root)

        test = self._serializer(root)
        if self._dry_run:
            return None

        test_fn = self._out_format % index if '%d' in self._out_format else self._out_format

        if self._population and self._keep_trees:
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

    def mutate(self, mutated_node, reserve):
        """
        Mutate a tree at a given position, i.e., discard and re-generate its
        sub-tree at the specified node.

        :param Rule mutated_node: The root of the sub-tree that should be
            re-generated.
        :param RuleSize reserve: Size budget that needs to be put in reserve
            before re-generating the sub-tree (distance of the sub-tree from
            the root of the tree, number of tokens outside the sub-tree).
            Practically, deduced from the initially specified limit.
        :return: The root of the mutated tree.
        :rtype: Rule
        """
        mutated_node = mutated_node.replace(self.generate(rule=mutated_node.name, reserve=reserve))
        return mutated_node.root

    def recombine(self, recipient_node, donor_node):
        """
        Recombine two trees at given positions where the nodes are compatible
        with each other (i.e., they share the same node name). One of the trees
        is called the recipient while the other is the donor. The sub-tree
        rooted at the specified node of the recipient is discarded and replaced
        by the sub-tree rooted at the specified node of the donor.

        :param Rule recipient_node: The root of the sub-tree in the recipient.
        :param Rule donor_node: The root of the sub-tree in the donor.
        :return: The root of the recombined tree.
        :rtype: Rule
        """
        if recipient_node.name != donor_node.name:
            raise ValueError(f'{recipient_node.name} cannot be replaced with {donor_node.name}')

        recipient_node = recipient_node.replace(donor_node)
        return recipient_node.root
