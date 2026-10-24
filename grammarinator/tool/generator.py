# Copyright (c) 2017-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import math
import os
import random
import re

from contextlib import nullcontext
from copy import deepcopy
from functools import partial
from os.path import abspath, dirname, join, split
from shutil import rmtree
from string import Formatter
from typing import Callable, Sequence

import xxhash

from inators import log as logging

from ..runtime import Annotations, Generator, DefaultModel, Individual, Listener, Model, ParentRule, Population, Rule, RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantifier, WeightedModel

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

    def __init__(self, generator_class: type[Generator]) -> None:
        """
        :param generator_class: The class of the wrapped generator.
        """
        self._generator_class: type[Generator] = generator_class  #: The class of the wrapped generator.
        # Exposing some class variables of the encapsulated generator.
        # In the generator class, they start with `_` to avoid any kind of
        # collision with rule names, so they start with `_` here as well.
        self._rule_sizes: dict[str, RuleSize] = generator_class._rule_sizes  # Sizes of the rules, used to determine the minimum size of the generated trees. Generated into the generator subclasses by processor.
        self._alt_sizes: tuple[tuple[RuleSize, ...], ...] = generator_class._alt_sizes  # Sizes of the alternatives of the rules, used to determine the minimum size of the generated trees. Generated into the generator subclasses by processor.
        self._quant_sizes: tuple[RuleSize, ...] = generator_class._quant_sizes  # Sizes of the quantifiers of the rules, used to determine the minimum size of the generated trees. Generated into the generator subclasses by processor.

    def __call__(self, limit: RuleSize | None = None) -> Generator:
        """
        Create a new generator instance.

        :param limit: The limit on the depth of the trees and on the number of
            tokens (number of unlexer rule calls), i.e., it must be possible to
            finish generation from the selected node so that the overall depth
            and token count of the tree does not exceed these limits (default:
            :class:`~grammarinator.runtime.RuleSize`. ``max``). Used to
            instantiate the generator.
        :return: The created generator instance.
        """
        return self._generator_class(limit=limit)


class DefaultGeneratorFactory(GeneratorFactory):
    """
    The default generator factory implementation. When called, a new generator
    instance is created backed by a new decision model instance and a set of
    newly created listener objects is attached.
    """

    def __init__(self, generator_class: type[Generator], *,
                 model_class: type[Model] | None = None, weights: dict[tuple[str, int, int], float] | None = None, probs: dict[tuple[str, int], float] | None = None,
                 listener_classes: list[type[Listener]] | None = None) -> None:
        """
        :param generator_class: The class of the generator to instantiate.
        :param model_class: The class of the model to instantiate. The model
            instance is used to instantiate the generator.
        :param weights: Initial multipliers of alternatives. Used to instantiate
            a :class:`~grammarinator.runtime.WeightedModel` wrapper around the
            model.
        :param probs: Initial custom  probabilities for quantifiers. Used to instantiate
            a :class:`~grammarinator.runtime.WeightedModel` wrapper around the
            model.
        :param listener_classes: List of listener classes to instantiate and
            attach to the generator.
        """
        super().__init__(generator_class)
        self._model_class: type[Model] = model_class or DefaultModel
        self._weights: dict[tuple[str, int, int], float] | None = weights
        self._probs: dict[tuple[str, int], float] | None = probs
        self._listener_classes: list[type[Listener]] = listener_classes or []

    def __call__(self, limit: RuleSize | None = None) -> Generator:
        """
        Create a new generator instance according to the settings specified for
        the factory instance and for this method.

        :param limit: The limit on the depth of the trees and on the number of
            tokens (number of unlexer rule calls), i.e., it must be possible to
            finish generation from the selected node so that the overall depth
            and token count of the tree does not exceed these limits (default:
            :class:`~grammarinator.runtime.RuleSize`. ``max``). Used to
            instantiate the generator.
        :return: The created generator instance.
        """
        model = self._model_class()
        if self._weights or self._probs:
            model = WeightedModel(model, weights=self._weights, probs=self._probs)

        listeners = []
        for listener_class in self._listener_classes:
            listeners.append(listener_class())

        generator = self._generator_class(model=model, listeners=listeners, limit=limit)

        return generator


class SwitchAlternativeModel(Model):
    """
    Decision model wrapper that, in the root rule of the generation, forces
    the given alternatives of some alternations (if they are possible) and
    avoids an alternative of another alternation (if any other alternative is
    possible there).
    """

    def __init__(self, model: Model, *, rule: str, forced_choices: dict[int, int], avoided_alt_idx: int, avoided_choice: int) -> None:
        """
        :param model: The underlying model.
        :param rule: Name of the root rule of the generation.
        :param forced_choices: Indices of the alternatives to choose, keyed by
            the indices of their alternations within the rule.
        :param avoided_alt_idx: Index of the alternation within the rule, where
            an alternative has to be avoided.
        :param avoided_choice: Index of the alternative to avoid.
        """
        self._model = model
        self._rule = rule
        self._forced_choices = forced_choices
        self._avoided_alt_idx = avoided_alt_idx
        self._avoided_choice = avoided_choice

    def choice(self, node: Rule, idx: int, weights: list[float]) -> int:
        """
        Apply the forced and avoided choices in the root rule, otherwise call
        the ``choice`` method of the underlying model.
        """
        if node.parent is None and node.name == self._rule:
            forced_choice = self._forced_choices.get(idx)
            if forced_choice is not None and forced_choice < len(weights) and weights[forced_choice] > 0:
                return forced_choice
            if idx == self._avoided_alt_idx and self._avoided_choice < len(weights):
                avoiding_weights = list(weights)
                avoiding_weights[self._avoided_choice] = 0
                if sum(avoiding_weights) > 0:
                    return self._model.choice(node, idx, avoiding_weights)
        return self._model.choice(node, idx, weights)

    def quantify(self, node: Rule, idx: int, cnt: int, start: int, stop: int | float, prob: float = 0.5) -> bool:
        """
        Trampoline to the ``quantify`` method of the underlying model.
        """
        return self._model.quantify(node, idx, cnt, start, stop, prob)

    def charset(self, node: Rule, idx: int, chars: tuple[int, ...]) -> str:
        """
        Trampoline to the ``charset`` method of the underlying model.
        """
        return self._model.charset(node, idx, chars)


class GeneratorTool:
    """
    Tool to create new test cases using the generator produced by
    ``grammarinator-process``.
    """

    def __init__(self, generator_factory: type[Generator] | GeneratorFactory, out_format: str, lock=None, rule: str | None = None, limit: RuleSize | None = None,
                 population: Population | None = None, keep_trees: bool = False,
                 generate: bool = True, mutate: bool = True, recombine: bool = True, unrestricted: bool = True,
                 allowlist: list[str] | None = None, blocklist: list[str] | None = None,
                 transformers: list[Callable[[Rule], Rule]] | None = None, serializer: Callable[[Rule], str] | None = None, memo_size: int = 0, unique_attempts: int = 2,
                 cleanup: bool = True, encoding: str = 'utf-8', errors: str = 'strict', dry_run: bool = False):
        """
        :param generator_factory: A callable that can produce instances of a
            generator. It is a generalization of a generator class: it has to
            instantiate a generator object, and it may also set the decision
            model and the listeners of the generator as well. It also has to
            expose some properties of the generator class necessary to guide
            generation or mutation. In the simplest case, it can be a
            ``grammarinator-process``-created subclass of :class:`Generator`,
            but in more complex scenarios a factory can be used, e.g., an
            instance of a subclass of :class:`GeneratorFactory`,
            like :class:`DefaultGeneratorFactory`.
        :param rule: Name of the rule to start generation from (default: the
            default rule of the generator).
        :param out_format: Test output description. It can be a file path
            pattern whose filename part may include the ``{id}``, ``{src}``,
            and ``{op}`` placeholders (in :meth:`str.format` syntax), which
            will be replaced by the index of the test case, the index of the
            test case that the current test case is based on (or the name of
            the source tree, if its index cannot be recovered), and the name
            of the creator (generator, mutator, or recombiner) that produced
            the test case, respectively. Placeholders without a value are
            replaced by ``-``. For backward compatibility, the filename may
            include the ``%d`` placeholder, which is equivalent to ``{id}``.
            Otherwise, it can be an empty string, which will result in
            printing the test case to the stdout (i.e., not saving to file
            system).
        :param lock: Lock object necessary when printing test cases in parallel
            (optional).
        :type lock: :class:`multiprocessing.Lock` | None
        :param limit: The limit on the depth of the trees and on the number of
            tokens (number of unlexer rule calls), i.e., it must be possible to
            finish generation from the selected node so that the overall depth
            and token count of the tree does not exceed these limits (default:
            :class:`~grammarinator.runtime.RuleSize`. ``max``).
        :param population: Tree pool for mutation and recombination, e.g., an
            instance of :class:`FilePopulation`.
        :param keep_trees: Keep generated trees to participate in further
            mutations or recombinations (otherwise, only the initial population
            will be mutated or recombined). It has effect only if population is
            defined.
        :param generate: Enable generating new test cases from scratch, i.e.,
            purely based on grammar.
        :param mutate: Enable mutating existing test cases, i.e., re-generate
            part of an existing test case based on grammar.
        :param recombine: Enable recombining existing test cases, i.e., replace
            part of a test case with a compatible part from another test case.
        :param unrestricted: Enable applying possibly grammar-violating
            creators.
        :param allowlist: List of mutators to allow (by default, all mutators
            are allowed).
        :param blocklist: List of mutators to block (by default, no mutators are
            blocked).
        :param transformers: List of transformers to be applied to postprocess
            the generated tree before serializing it.
        :param serializer: A serializer that takes a tree and produces a string
            from it (default: :class:`str`). See
            :func:`grammarinator.runtime.simple_space_serializer` for a simple
            solution that concatenates tokens with spaces.
        :param memo_size: The number of most recently created unique tests
            memoized (default: 0).
        :param unique_attempts: The limit on how many times to try to generate a
            unique (i.e., non-memoized) test case. It has no effect if
            ``memo_size`` is 0 (default: 2).
        :param cleanup: Enable deleting the generated tests at :meth:`__exit__`.
        :param encoding: Output file encoding.
        :param errors: Encoding error handling scheme.
        :param dry_run: Enable or disable the saving or printing of the result
            of generation.
        """

        self._generator_factory = generator_factory
        self._transformers = transformers or []
        self._serializer = serializer or str
        self._rule = rule

        self._out_format = out_format
        self._out_dir, self._out_name = split(out_format)
        # Convert the legacy %d placeholder to {id}.
        self._out_name = self._out_name.replace('%d', '{id}', 1)
        # Fail early on invalid patterns.
        try:
            self._out_name.format(id=0, src='-', op='-')
        except (KeyError, IndexError, ValueError) as e:
            raise ValueError(f'Invalid output file name pattern: {out_format!r}') from e

        # Build the regex that recovers {id} from the names created by the
        # pattern.
        regex = ''
        for literal, field, _, _ in Formatter().parse(self._out_name):
            regex += re.escape(literal)
            if field is not None:
                regex += '.*?' if field != 'id' else '(?P=id)' if '(?P<id>' in regex else '(?P<id>.*?)'
        self._src_regex = re.compile(regex)

        if out_format and not dry_run:
            os.makedirs(abspath(self._out_dir), exist_ok=True)

        self._lock = lock or nullcontext()
        self._limit = limit or RuleSize.max
        self._population = population
        self._enable_generation = generate
        self._enable_mutation = mutate
        self._enable_recombination = recombine
        self._keep_trees = keep_trees
        self._memo: dict[int, None] = {}  # NOTE: value associated to test is unimportant, but dict keeps insertion order while set does not
        self._memo_size = memo_size
        self._unique_attempts = max(unique_attempts, 1)
        self._cleanup = cleanup
        self._encoding = encoding
        self._errors = errors
        self._dry_run = dry_run
        self._last_mutator = ''
        self._last_individual = ''

        self.allowlist = allowlist or []
        self.blocklist = blocklist or []

        self._generators: list[Callable[[Individual | None, Individual | None], Rule | None]] = []
        self._mutators: list[Callable[[Individual | None, Individual | None], Rule | None]] = []
        self._recombiners: list[Callable[[Individual | None, Individual | None], Rule | None]] = []

        if generate:
            self._allow_creator(self._generators, "generate", self.generate)

        if mutate:
            self._allow_creator(self._mutators, "regenerate_rule", self.regenerate_rule)
            self._allow_creator(self._mutators, "switch_alternative_keep_children", self.switch_alternative_keep_children)
            self._allow_creator(self._mutators, "delete_quantified", self.delete_quantified)
            self._allow_creator(self._mutators, "replicate_quantified", self.replicate_quantified)
            self._allow_creator(self._mutators, "replicate_with_variation", self.replicate_with_variation)
            self._allow_creator(self._mutators, "shuffle_quantifieds", self.shuffle_quantifieds)
            self._allow_creator(self._mutators, "hoist_rule", self.hoist_rule)
            self._allow_creator(self._mutators, "pump_recursion", self.pump_recursion)
            self._allow_creator(self._mutators, "swap_local_nodes", self.swap_local_nodes)
            self._allow_creator(self._mutators, "copy_local_node", self.copy_local_node)
            self._allow_creator(self._mutators, "insert_local_node", self.insert_local_node)
            self._allow_creator(self._mutators, "merge_names", self.merge_names)
            if unrestricted:
                self._allow_creator(self._mutators, "unrestricted_delete", self.unrestricted_delete)
                self._allow_creator(self._mutators, "unrestricted_hoist_rule", self.unrestricted_hoist_rule)

        if recombine:
            self._allow_creator(self._recombiners, "replace_node", self.replace_node)
            self._allow_creator(self._recombiners, "insert_quantified", self.insert_quantified)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Delete the output directory if the tests were saved to files and if
        ``cleanup`` was enabled.
        """
        if self._cleanup and self._out_format and not self._dry_run:
            rmtree(dirname(self._out_format))

    def _allow_creator(self, creator_map: list[Callable[[Individual | None, Individual | None], Rule | None]], creator_name: str, creator: Callable[[Individual | None, Individual | None], Rule | None]):
        if creator_name not in self.blocklist and (not self.allowlist or creator_name in self.allowlist):
            creator_map.append(creator)

    def print_mutator(self, fmt: str, *args) -> None:
        logger.debug('GrammarinatorMutator [%s]', fmt.format(*args))

    def create_test(self, index: int) -> str | None:
        """
        Create a new test case with a randomly selected generator method from
        the available options (see :meth:`generate`, :meth:`mutate`, and
        :meth:`recombine`). The generated tree is transformed, serialized and
        saved according to the parameters used to initialize the current tool
        object.

        :param index: Index of the test case to be generated.
        :return: Path to the generated serialized test file. It may be empty if
            the tool object was initialized with an empty ``out_format`` or
            ``None`` if ``dry_run`` was enabled, and hence the test file was not
            saved.
        """
        for attempt in range(1, self._unique_attempts + 1):
            root = self.create()
            if not root:
                logger.debug("test case #%d, attempt %d/%d: could not be generated", index, attempt, self._unique_attempts)
                continue
            test = self._serializer(root)
            if self._memoize_test(test):
                break
            logger.debug("test case #%d, attempt %d/%d: already generated among the last %d unique test cases", index, attempt, self._unique_attempts, len(self._memo))
        if self._dry_run or not root:
            return None

        match = self._src_regex.fullmatch(self._last_individual)
        src = match.groupdict().get('id', self._last_individual) if match else self._last_individual
        test_fn = join(self._out_dir, self._out_name.format(id=index, src=src or '-', op=self._last_mutator or '-'))

        if self._population is not None and self._keep_trees:
            self._population.add_individual(root, path=test_fn)

        if test_fn:
            with open(test_fn, 'w', encoding=self._encoding, errors=self._errors, newline='') as f:
                f.write(test)
        else:
            with self._lock:
                print(test)

        return test_fn

    def _memoize_test(self, input: str) -> bool:
        # Memoize the (hash of the) test case. The size of the memo is capped
        # by ``memo_size``, i.e., it contains at most that many test cases.
        # Returns ``False`` if the test case was already in the memo, ``True``
        # if it got added now (or memoization is disabled by ``memo_size=0``).
        # When the memo is full and a new test case is added, the oldest entry
        # is evicted.
        if self._memo_size < 1:
            return True
        test = xxhash.xxh3_64_intdigest(input.encode(encoding=self._encoding, errors=self._errors))
        if test in self._memo:
            return False
        self._memo[test] = None
        if len(self._memo) > self._memo_size:
            del self._memo[next(iter(self._memo))]
        return True

    def _select_creator(self, creators: list[Callable[[Individual | None, Individual | None], Rule | None]], individual1: Individual | None, individual2: Individual | None) -> Callable[[Individual | None, Individual | None], Rule | None]:  # pylint: disable=unused-argument
        # NOTE: May be overridden.
        return random.choice(creators)

    def _create_tree(self, creators: list[Callable[[Individual | None, Individual | None], Rule | None]], individual1: Individual | None, individual2: Individual | None) -> Rule | None:
        # Note: creators is potentially modified (creators that return None are removed). Always ensure it is a copy when calling this method.
        while creators:
            creator = self._select_creator(creators, individual1, individual2)
            if individual1 is not None:
                logger.trace("Original test: '%s'", self._serializer(individual1.root))
            root = creator(individual1, individual2)
            if root:
                self._last_mutator = creator.__name__
                self._last_individual = (individual1.name or '') if individual1 and creator not in self._generators else ''
                break
            creators.remove(creator)
        else:
            logger.warning("No test creators could produce a tree")
            return None

        for transformer in self._transformers:
            root = transformer(root)
        return root

    def create(self) -> Rule | None:
        """
        Create a new tree with a randomly selected generator method from the
        available options (see :meth:`generate`, :meth:`mutate`, and
        :meth:`recombine`). The generated tree is also transformed according to
        the parameters used to initialize the current tool object.

        :return: The root of the created tree.
        """
        individual1, individual2 = (self._ensure_individuals(None, None)) if self._population else (None, None)
        creators = []
        creators.extend(self._generators)
        if self._population:
            creators.extend(self._mutators)
            creators.extend(self._recombiners)
        return self._create_tree(creators, individual1, individual2)

    def mutate(self, individual: Individual | None = None) -> Rule | None:
        """
        Dispatcher method for mutation operators: it picks one operator randomly
        and creates a new tree by applying the operator to an individual. The
        generated tree is also transformed according to the parameters used to
        initialize the current tool object.

        Supported mutation operators: :meth:`regenerate_rule`,
        :meth:`delete_quantified`, :meth:`replicate_quantified`,
        :meth:`shuffle_quantifieds`, :meth:`hoist_rule`,
        :meth:`unrestricted_delete`, :meth:`unrestricted_hoist_rule`,
        :meth:`swap_local_nodes`, :meth:`insert_local_node`

        :param individual: The population item to be mutated.
        :return: The root of the mutated tree.
        """
        # NOTE: Intentionally does not check self._enable_mutation!
        # If you call this explicitly, then so be it, even if mutation is disabled.
        # If individual is None, population MUST exist.
        individual = self._ensure_individual(individual)
        if not individual.root.children:  # type: ignore[attr-defined]
            logger.debug('Mutate empty tree. Regenerate %s', individual.root.name)
            root = self.generate(rule=individual.root.name)
            for transformer in self._transformers:
                root = transformer(root)  # type: ignore[assignment]
            return root
        return self._create_tree(self._mutators[:], individual, None)

    def recombine(self, individual1: Individual | None = None, individual2: Individual | None = None) -> Rule | None:
        """
        Dispatcher method for recombination operators: it picks one operator
        randomly and creates a new tree by applying the operator to an
        individual. The generated tree is also transformed according to the
        parameters used to initialize the current tool object.

        Supported recombination operators: :meth:`replace_node`,
        :meth:`insert_quantified`

        :param individual1: The population item to be used as a recipient during
            crossover.
        :param individual2: The population item to be used as a donor during
            crossover.
        :return: The root of the recombined tree.
        """
        # NOTE: Intentionally does not check self._enable_recombination!
        # If you call this explicitly, then so be it, even if recombination is disabled.
        # If any of the individuals is None, population MUST exist.
        individual1, individual2 = self._ensure_individuals(individual1, individual2)
        return self._create_tree(self._recombiners[:], individual1, individual2)

    def generate(self, _individual1: Individual | None = None, _individual2: Individual | None = None, *, rule: str | None = None, reserve: RuleSize | None = None,
                 wrap_model: Callable[[Model], Model] | None = None) -> UnlexerRule | UnparserRule:
        """
        Instantiate a new generator and generate a new tree from scratch.

        :param rule: Name of the rule to start generation from.
        :param reserve: Size budget that needs to be put in reserve before
            generating the tree. Practically, deduced from the initially
            specified limit. (default values: 0, 0)
        :param wrap_model: Function to wrap the decision model of the
            generator into another model (optional).
        :return: The root of the generated tree.
        """
        # NOTE: Intentionally does not check self._enable_generation!
        # If you call this explicitly, then so be it, even if generation is disabled.
        reserve = reserve if reserve is not None else RuleSize()
        generator = self._generator_factory(limit=self._limit - reserve)
        if wrap_model:
            generator._model = wrap_model(generator._model)
        rule = rule or self._rule or generator._default_rule.__name__
        if not hasattr(generator, rule):
            logger.error('Rule %s not found.', rule)
            raise AttributeError(rule)
        self.print_mutator('{}: {}', self.generate.__name__, rule)
        return getattr(generator, rule)()

    def _ensure_individual(self, individual: Individual | None) -> Individual:
        if individual is None:
            assert self._population is not None
            individual = self._population.select_individual()
        return individual

    def _ensure_individuals(self, individual1: Individual | None, individual2: Individual | None) -> tuple[Individual, Individual]:
        individual1 = self._ensure_individual(individual1)
        if individual2 is None:
            assert self._population is not None
            individual2 = self._population.select_individual(individual1)
        return individual1, individual2

    def regenerate_rule(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Mutate a tree at a random position, i.e., discard and re-generate its
        sub-tree at a randomly selected node.

        :param individual: The population item to be mutated.
        :return: The root of the mutated tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations

        # Filter items from the nodes of the selected tree that can be regenerated
        # within the current maximum depth and token limit (except immutable nodes).
        root_tokens = annot.node_tokens[root]
        options = []
        for (rule_name,), nodes in annot.rules_by_name.items():
            rule_size = self._generator_factory._rule_sizes.get(rule_name)
            if rule_size is None:
                logger.error('Unknown rule name in generation: %s.', rule_name)
                continue
            for node in nodes:
                if (node.parent is not None
                        and annot.node_levels[node] + rule_size.depth < self._limit.depth
                        and root_tokens - annot.node_tokens[node] + rule_size.tokens < self._limit.tokens):
                    options.append(node)
        if options:
            mutated_node = random.choice(options)
            self.print_mutator('{}: {}', self.regenerate_rule.__name__, mutated_node.name)
            reserve = RuleSize(depth=annot.node_levels[mutated_node],
                               tokens=root_tokens - annot.node_tokens[mutated_node])
            mutated_node = mutated_node.replace(self.generate(rule=mutated_node.name, reserve=reserve))  # type: ignore[assignment]
            return mutated_node.root

        logger.trace('%s failed.', self.regenerate_rule.__name__)
        return None

    def switch_alternative_keep_children(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select an alternative node directly below a rule node, and regenerate
        the rule node so that a different alternative is chosen there. Then,
        put the old rule children of the node (i.e., the rule nodes below it
        but not below another rule node) in place of the newly generated ones
        of the same rule, in order. E.g., ``a + b`` may become ``a * b`` or
        ``( a )``.

        :param individual: The population item to be mutated.
        :return: The root of the mutated tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations

        # Only alternatives are considered that are below their rule node only
        # via other alternatives (and not via quantifiers). So, if the choices
        # of these ancestor alternatives are kept when the rule is regenerated,
        # the alternation of the selected alternative is reached exactly once.
        root_tokens = annot.node_tokens[root]
        options = []
        for nodes in annot.nodes_by_name.values():
            for node in nodes:
                if not isinstance(node, UnparserRuleAlternative):
                    continue
                forced_choices = {}
                rule_node = node.parent
                while isinstance(rule_node, UnparserRuleAlternative):
                    forced_choices[rule_node.alt_idx] = rule_node.idx
                    rule_node = rule_node.parent
                if not isinstance(rule_node, UnparserRule) or rule_node is root:
                    continue
                rule_size = self._generator_factory._rule_sizes.get(rule_node.name)
                if (rule_size is not None
                        and annot.node_levels[rule_node] + rule_size.depth < self._limit.depth
                        and root_tokens - annot.node_tokens[rule_node] + rule_size.tokens < self._limit.tokens):
                    options.append((node, rule_node, forced_choices))

        def rule_children(node: ParentRule) -> list[Rule]:
            # Rule nodes below a rule node that are not below another rule node.
            children: list[Rule] = []
            for child in node.children:
                if isinstance(child, (UnparserRule, UnlexerRule)):
                    if not isinstance(child, UnlexerRule) or not child.immutable:
                        children.append(child)
                else:
                    children.extend(rule_children(child))  # type: ignore[arg-type]
            return children

        def find_alternative(node: ParentRule, alt_idx: int) -> UnparserRuleAlternative | None:
            # The alternative node of the given alternation below a rule node,
            # if it is not below another rule node.
            for child in node.children:
                if isinstance(child, UnparserRuleAlternative) and child.alt_idx == alt_idx:
                    return child
                if isinstance(child, ParentRule) and not isinstance(child, UnparserRule):
                    found = find_alternative(child, alt_idx)
                    if found:
                        return found
            return None

        for alt_node, rule_node, forced_choices in random.sample(options, k=len(options)):
            reserve = RuleSize(depth=annot.node_levels[rule_node], tokens=root_tokens - annot.node_tokens[rule_node])
            new_rule_node = self.generate(rule=rule_node.name, reserve=reserve,
                                          wrap_model=partial(SwitchAlternativeModel, rule=rule_node.name, forced_choices=forced_choices, avoided_alt_idx=alt_node.alt_idx, avoided_choice=alt_node.idx))
            new_alt_node = find_alternative(new_rule_node, alt_node.alt_idx)  # type: ignore[arg-type]
            if new_alt_node is None or new_alt_node.idx == alt_node.idx:
                continue

            # Put the old rule children in place of the new ones of the same
            # rule, in order, as long as the token limit allows.
            old_children_by_name: dict[str, list[Rule]] = {}
            for old_child in rule_children(rule_node):
                old_children_by_name.setdefault(old_child.name, []).append(old_child)

            new_annot = Annotations(new_rule_node)
            tokens = root_tokens - annot.node_tokens[rule_node] + new_annot.node_tokens[new_rule_node]
            for new_child in rule_children(new_rule_node):  # type: ignore[arg-type]
                candidates = old_children_by_name.get(new_child.name)
                if not candidates:
                    continue
                new_tokens = tokens - new_annot.node_tokens[new_child] + annot.node_tokens[candidates[0]]
                if new_tokens > self._limit.tokens:
                    continue
                new_child.replace(candidates.pop(0))
                tokens = new_tokens

            self.print_mutator('{}: {}, {}, {}', self.switch_alternative_keep_children.__name__, rule_node.name, alt_node.alt_idx, alt_node.idx)
            rule_node.replace(new_rule_node)
            return root
        logger.trace('%s failed.', self.switch_alternative_keep_children.__name__)
        return None

    def replace_node(self, recipient_individual: Individual | None = None, donor_individual: Individual | None = None) -> Rule | None:
        """
        Recombine two trees at random positions where the nodes are compatible
        with each other (i.e., they share the same node name). One of the trees
        is called the recipient while the other is the donor. The sub-tree
        rooted at a random node of the recipient is discarded and replaced by
        the sub-tree rooted at a random node of the donor.

        :param recipient_individual: The population item to be used as a
            recipient during crossover.
        :param donor_individual: The population item to be used as a donor
            during crossover.
        :return: The root of the recombined tree.
        """
        recipient_individual, donor_individual = self._ensure_individuals(recipient_individual, donor_individual)
        recipient_root, recipient_annot = recipient_individual.root, recipient_individual.annotations
        donor_annot = donor_individual.annotations

        recipient_lookup: dict[tuple[str | int, ...], Sequence[Rule]] = dict(recipient_annot.nodes_by_name)
        donor_lookup: dict[tuple[str | int, ...], Sequence[Rule]] = dict(donor_annot.nodes_by_name)
        common_types = sorted(set(recipient_lookup.keys()) & set(donor_lookup.keys()))

        recipient_options = [(rule_name, node) for rule_name in common_types for node in recipient_lookup[rule_name] if node.parent]
        recipient_root_tokens = recipient_annot.node_tokens[recipient_root]
        # Shuffle suitable nodes with sample.
        for rule_name, recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            donor_options = donor_lookup[rule_name]
            recipient_node_level = recipient_annot.node_levels[recipient_node]
            recipient_node_tokens = recipient_annot.node_tokens[recipient_node]
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth limit.
                if (recipient_node_level + donor_annot.node_depths[donor_node] <= self._limit.depth
                        and recipient_root_tokens - recipient_node_tokens + donor_annot.node_tokens[donor_node] < self._limit.tokens):
                    self.print_mutator('{}: {}', self.replace_node.__name__, recipient_node.rule_name)
                    recipient_node.replace(donor_node)
                    return recipient_root

        logger.trace('%s failed.', self.replace_node.__name__)
        return None

    def insert_quantified(self, recipient_individual: Individual | None = None, donor_individual: Individual | None = None) -> Rule | None:
        """
        Selects two compatible quantifier nodes from two trees randomly and if
        the quantifier node of the recipient tree is not full (the number of its
        children is less than the maximum count), then add one new child to it
        at a random position from the children of donors quantifier node.

        :param recipient_individual: The population item to be used as a
            recipient during crossover.
        :param donor_individual: The population item to be used as a donor
            during crossover.
        :return: The root of the extended tree.
        """
        recipient_individual, donor_individual = self._ensure_individuals(recipient_individual, donor_individual)
        recipient_root, recipient_annot = recipient_individual.root, recipient_individual.annotations
        donor_annot = donor_individual.annotations

        common_types = sorted(set(recipient_annot.quants_by_name.keys()) & set(donor_annot.quants_by_name.keys()))
        recipient_options = [(name, node) for name in common_types for node in recipient_annot.quants_by_name[name] if len(node.children) < node.stop]
        recipient_root_tokens = recipient_annot.node_tokens[recipient_root]
        for rule_name, recipient_node in random.sample(recipient_options, k=len(recipient_options)):
            recipient_node_level = recipient_annot.node_levels[recipient_node]
            donor_options = [quantified for quantifier in donor_annot.quants_by_name[rule_name] for quantified in quantifier.children]
            for donor_node in random.sample(donor_options, k=len(donor_options)):
                # Make sure that the output tree won't exceed the depth and token limits.
                if (recipient_node_level + donor_annot.node_depths[donor_node] <= self._limit.depth
                        and recipient_root_tokens + donor_annot.node_tokens[donor_node] < self._limit.tokens):
                    self.print_mutator('{}: {}, {}', self.insert_quantified.__name__, recipient_node.rule_name, recipient_node.idx)
                    recipient_node.insert_child(random.randint(0, len(recipient_node.children)), donor_node)
                    return recipient_root
        logger.trace('%s failed.', self.insert_quantified.__name__)
        return None

    def delete_quantified(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Removes an optional subtree randomly from a quantifier node.

        :param individual: The population item to be mutated.
        :return: The root of the modified tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [child for node in annot.quants if len(node.children) > node.start for child in node.children]
        if options:
            removed_node = random.choice(options)
            self.print_mutator('{}: {}, {}', self.delete_quantified.__name__, removed_node.rule_name, removed_node.parent.idx)  # type: ignore[union-attr]
            removed_node.remove()
            return root
        logger.trace('%s failed.', self.delete_quantified.__name__)
        return None

    def unrestricted_delete(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Remove a subtree rooted in any kind of rule node randomly without any
        further restriction.

        :param individual: The population item to be mutated.
        :return: The root of the modified tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [node for node in annot.rules if node != root]
        if options:
            removed_node = random.choice(options)
            self.print_mutator('{}: {}', self.unrestricted_delete.__name__, removed_node.name)
            removed_node.remove()
            return root
        logger.trace('%s failed.', self.unrestricted_delete.__name__)
        return None

    def replicate_quantified(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select a quantified sub-tree randomly, replicate it and insert it again
        if the maximum quantification count is not reached yet.

        :param individual: The population item to be mutated.
        :return: The root of the modified tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        root_options = [node for node in annot.quants if node.stop > len(node.children)]
        recipient_root_tokens = annot.node_tokens[root]
        node_options = [child for root in root_options for child in root.children if
                        recipient_root_tokens < recipient_root_tokens + annot.node_tokens[child] <= self._limit.tokens]
        if node_options:
            node_to_repeat = random.choice(node_options)
            max_repeat = (self._limit.tokens - recipient_root_tokens) // annot.node_tokens[node_to_repeat] if self._limit.tokens != RuleSize.max.tokens else 1
            # Draw the number of copies log-uniformly: small numbers are likely, but large ones remain possible.
            repeat = min(int(max_repeat), int(math.exp(random.uniform(0, math.log(max_repeat + 1))))) if max_repeat > 1 else 1
            for _ in range(repeat):
                node_to_repeat.parent.insert_child(idx=random.randint(0, len(node_to_repeat.parent.children)), node=deepcopy(node_to_repeat))  # type: ignore[union-attr]
            self.print_mutator('{}: {}, {}', self.replicate_quantified.__name__, node_to_repeat.rule_name, node_to_repeat.parent.idx)  # type: ignore[union-attr]
            return root
        logger.trace('%s failed.', self.replicate_quantified.__name__)
        return None

    def replicate_with_variation(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select a quantified sub-tree randomly and insert copies of it if the
        maximum quantification count is not reached yet, similarly to
        :meth:`replicate_quantified`. However, a randomly selected rule node is
        re-generated in each copy, so that the copies differ from each other.

        :param individual: The population item to be mutated.
        :return: The root of the modified tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        root_options = [node for node in annot.quants if node.stop > len(node.children)]
        root_tokens = annot.node_tokens[root]
        node_options = [child for root in root_options for child in root.children if
                        root_tokens < root_tokens + annot.node_tokens[child] <= self._limit.tokens]
        if not node_options:
            logger.trace('%s failed.', self.replicate_with_variation.__name__)
            return None

        node_to_repeat = random.choice(node_options)
        parent = node_to_repeat.parent
        assert isinstance(parent, UnparserRuleQuantifier)
        node_level = annot.node_levels[node_to_repeat]
        node_tokens = annot.node_tokens[node_to_repeat]
        max_repeat = (self._limit.tokens - root_tokens) // node_tokens if self._limit.tokens != RuleSize.max.tokens else 1
        # Draw the number of copies log-uniformly: small numbers are likely, but large ones remain possible.
        repeat = min(int(max_repeat), int(math.exp(random.uniform(0, math.log(max_repeat + 1))))) if max_repeat > 1 else 1
        inserted = 0
        for _ in range(repeat):
            if root_tokens + node_tokens > self._limit.tokens:
                break
            copy = deepcopy(node_to_repeat)

            # Regenerate a random rule node in each copy to make the copies
            # differ. As regeneration may give back the same tokens (e.g., for
            # literals), a few rule nodes are tried. If none of them changes,
            # no more copies are inserted.
            copy_annot = Annotations(copy)
            variants = []
            for (rule_name,), nodes in copy_annot.rules_by_name.items():
                rule_size = self._generator_factory._rule_sizes.get(rule_name)
                if rule_size is None:
                    continue
                for node in nodes:
                    if (node_level + copy_annot.node_levels[node] + rule_size.depth < self._limit.depth
                            and root_tokens + node_tokens - copy_annot.node_tokens[node] + rule_size.tokens < self._limit.tokens):
                        variants.append(node)
            varied = False
            for varied_node in random.sample(variants, k=min(len(variants), 3)):
                varied_tokens = copy_annot.node_tokens[varied_node]
                reserve = RuleSize(depth=node_level + copy_annot.node_levels[varied_node],
                                   tokens=root_tokens + node_tokens - varied_tokens)
                new_node = self.generate(rule=varied_node.name, reserve=reserve)
                if new_node.equalTokens(varied_node):
                    continue
                varied_node.replace(new_node)
                root_tokens += node_tokens + Annotations(new_node).node_tokens[new_node] - varied_tokens
                varied = True
                break
            if not varied:
                break

            parent.insert_child(idx=random.randint(0, len(parent.children)), node=copy)
            inserted += 1
        if not inserted:
            logger.trace('%s failed.', self.replicate_with_variation.__name__)
            return None
        self.print_mutator('{}: {}, {}, {}', self.replicate_with_variation.__name__, node_to_repeat.rule_name, parent.idx, inserted)
        return root

    def shuffle_quantifieds(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select a quantifier node and shuffle its quantified sub-trees.

        :param individual: The population item to be mutated.
        :return: The root of the modified tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [node for node in annot.quants if len(node.children) > 1]
        if options:
            node_to_shuffle = random.choice(options)
            random.shuffle(node_to_shuffle.children)
            self.print_mutator('{}: {}, {}', self.shuffle_quantifieds.__name__, node_to_shuffle.rule_name, node_to_shuffle.idx)
            return root
        logger.trace('%s failed.', self.shuffle_quantifieds.__name__)
        return None

    def hoist_rule(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select an individual of the population to be mutated and select two rule
        nodes from it which share the same rule name and are in
        ancestor-descendant relationship making possible for the descendant to
        replace its ancestor.

        :param individual: The population item to be mutated.
        :return: The root of the hoisted tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        for rule in random.sample(annot.rules, k=len(annot.rules)):
            parent = rule.parent
            while parent:
                if parent.name == rule.name:
                    self.print_mutator('{}: {}', self.hoist_rule.__name__, parent.name)
                    parent.replace(rule)
                    return root
                parent = parent.parent
        logger.trace('%s failed.', self.hoist_rule.__name__)
        return None

    def pump_recursion(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select two rule nodes from the input individual which share the same
        rule name and are in ancestor-descendant relationship, and repeat the
        part of the ancestor's sub-tree that is not covered by the descendant
        (i.e., the ring between them) a random number of times, nesting the
        copies into each other. The descendant gets into the innermost copy.
        This is the inverse of :meth:`hoist_rule`.

        :param individual: The population item to be mutated.
        :return: The root of the pumped tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        root_tokens = annot.node_tokens[root]
        for rule in random.sample(annot.rules, k=len(annot.rules)):
            if not isinstance(rule, UnparserRule):
                continue

            ancestors = []
            parent = rule.parent
            while parent:
                if parent.name == rule.name:
                    ancestors.append(parent)
                parent = parent.parent

            for ancestor in random.sample(ancestors, k=len(ancestors)):
                ring_levels = annot.node_levels[rule] - annot.node_levels[ancestor]
                ring_tokens = annot.node_tokens[ancestor] - annot.node_tokens[rule]
                depth_budget = self._limit.depth - annot.node_levels[rule] - annot.node_depths[ancestor]
                if ring_tokens <= 0 or depth_budget < 0 or root_tokens + ring_tokens > self._limit.tokens:
                    continue
                max_pump = 0
                if self._limit.depth != RuleSize.max.depth:
                    max_pump = int(depth_budget // ring_levels) + 1
                if self._limit.tokens != RuleSize.max.tokens:
                    token_pump = int((self._limit.tokens - root_tokens) // ring_tokens)
                    max_pump = min(max_pump, token_pump) if max_pump > 0 else token_pump
                pump = random.randint(1, max_pump) if max_pump > 1 else 1

                path = []
                node = rule
                while node is not ancestor:
                    path.append(node.parent.children.index(node))  # type: ignore[union-attr]
                    node = node.parent  # type: ignore[assignment]
                path.reverse()

                outer_ring, hole = None, None
                for _ in range(pump):
                    ring = deepcopy(ancestor)
                    ring_hole: Rule = ring
                    for idx in path:
                        ring_hole = ring_hole.children[idx]  # type: ignore[attr-defined]
                    if outer_ring is None:
                        outer_ring = ring
                    else:
                        hole.replace(ring)  # type: ignore[union-attr]
                    hole = ring_hole
                rule.replace(outer_ring)  # type: ignore[arg-type]
                hole.replace(rule)  # type: ignore[union-attr]
                self.print_mutator('{}: {}, {}', self.pump_recursion.__name__, rule.name, pump)
                return root
        logger.trace('%s failed.', self.pump_recursion.__name__)
        return None

    def unrestricted_hoist_rule(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select two rule nodes from the input individual which are in
        ancestor-descendant relationship (without type compatibility check) and
        replace the ancestor with the selected descendant.

        :param individual: The population item to be mutated.
        :return: The root of the modified tree.
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
                hoist_parent = random.choice(options)
                self.print_mutator('{}: {}, {}', self.unrestricted_hoist_rule.__name__, hoist_parent.name, rule.name)
                hoist_parent.replace(rule)
                return root
        logger.trace('%s failed.', self.unrestricted_hoist_rule.__name__)
        return None

    def swap_local_nodes(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Swap two non-overlapping subtrees at random positions in a single test
        where the nodes are compatible with each other (i.e., they share the
        same node name).

        :param individual: The population item to be mutated
        :return: The root of the mutated tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations

        options: dict[tuple[str | int, ...], Sequence[Rule]] = dict(annot.nodes_by_name)
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
                            or second_node_level + first_node_depth > self._limit.depth):
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
                    assert first_parent is not None and second_parent is not None, 'Both nodes must have a parent.'
                    first_parent.children[first_parent.children.index(first_node)] = second_node
                    second_parent.children[second_parent.children.index(second_node)] = first_node
                    first_node.parent = second_parent
                    second_node.parent = first_parent
                    self.print_mutator('{}: {}', self.swap_local_nodes.__name__, first_node.rule_name)
                    return root
        logger.trace('%s failed.', self.swap_local_nodes.__name__)
        return None

    def copy_local_node(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Replace a subtree at a random position in a single test with a copy of
        another compatible subtree (i.e., one that shares the same node name)
        of the same test.

        :param individual: The population item to be mutated
        :return: The root of the mutated tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        root_tokens = annot.node_tokens[root]

        options: dict[tuple[str | int, ...], Sequence[Rule]] = dict(annot.nodes_by_name)
        for _, nodes in random.sample(list(options.items()), k=len(options)):
            # Skip node types without two instances.
            if len(nodes) < 2:
                continue

            shuffled = random.sample(nodes, k=len(nodes))
            for recipient_node in shuffled:
                recipient_node_level = annot.node_levels[recipient_node]
                recipient_node_tokens = annot.node_tokens[recipient_node]
                for donor_node in shuffled:
                    if (donor_node is recipient_node
                            or recipient_node_level + annot.node_depths[donor_node] > self._limit.depth
                            or root_tokens - recipient_node_tokens + annot.node_tokens[donor_node] > self._limit.tokens
                            or recipient_node.equalTokens(donor_node)):
                        continue

                    # The donor is copied before the replacement, so it may be
                    # an ancestor or a descendant of the recipient.
                    self.print_mutator('{}: {}', self.copy_local_node.__name__, recipient_node.rule_name)
                    recipient_node.replace(deepcopy(donor_node))
                    return root
        logger.trace('%s failed.', self.copy_local_node.__name__)
        return None

    def insert_local_node(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select two compatible quantifier nodes from a single test and insert a
        random quantified subtree of the second one into the first one at a
        random position, while the quantifier restrictions are ensured.

        :param individual: The population item to be mutated
        :return: The root of the mutated tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations
        options = [quantifiers for quantifiers in annot.quants_by_name.values() if len(quantifiers) > 1]
        if not options:
            logger.trace('%s failed.', self.insert_local_node.__name__)
            return None

        root_tokens = annot.node_tokens[root]
        for quantifiers in random.sample(options, k=len(options)):
            shuffled = random.sample(quantifiers, k=len(quantifiers))
            for i, recipient_node in enumerate(shuffled[:-1]):
                if len(recipient_node.children) >= recipient_node.stop:
                    continue

                recipient_node_level = annot.node_levels[recipient_node]
                for donor_quantifier in shuffled[i + 1:]:
                    for donor_quantified_node in donor_quantifier.children:
                        if (recipient_node_level + annot.node_depths[donor_quantified_node] <= self._limit.depth
                                and root_tokens + annot.node_tokens[donor_quantified_node] <= self._limit.tokens):
                            recipient_node.insert_child(random.randint(0, len(recipient_node.children)) if recipient_node.children else 0,
                                                        deepcopy(donor_quantified_node))
                            self.print_mutator('{}: {}, {}', self.insert_local_node.__name__, recipient_node.rule_name, recipient_node.idx)
                            return root
        logger.trace('%s failed.', self.insert_local_node.__name__)
        return None

    def merge_names(self, individual: Individual | None = None, _=None) -> Rule | None:
        """
        Select a lexer rule that has tokens with at least two different texts
        in a single test, and rewrite all the tokens having one of the texts to
        another text of the same lexer rule from the same test. E.g., all
        occurrences of an identifier are renamed to another identifier already
        used in the test.

        :param individual: The population item to be mutated
        :return: The root of the mutated tree.
        """
        individual = self._ensure_individual(individual)
        root, annot = individual.root, individual.annotations

        # Group the tokens of each lexer rule by their text and keep the lexer
        # rules that have at least two different texts in the tree.
        options = []
        for (rule_name,), nodes in annot.rules_by_name.items():
            if not rule_name or not isinstance(nodes[0], UnlexerRule):
                continue
            tokens_by_src: dict[str, list[UnlexerRule]] = {}
            for node in nodes:
                if node.src:  # type: ignore[union-attr]
                    tokens_by_src.setdefault(node.src, []).append(node)  # type: ignore[union-attr, arg-type]
            if len(tokens_by_src) > 1:
                options.append(tokens_by_src)
        if not options:
            logger.trace('%s failed.', self.merge_names.__name__)
            return None

        tokens_by_src = random.choice(options)
        from_src, to_src = random.sample(list(tokens_by_src.keys()), k=2)
        from_tokens = tokens_by_src[from_src]
        self.print_mutator('{}: {}, {} -> {}', self.merge_names.__name__, from_tokens[0].name, from_src, to_src)
        for token in from_tokens:
            token.src = to_src
        return root
