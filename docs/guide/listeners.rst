=========
Listeners
=========

Listeners are specific kind of actions that are executed before and after
processing (recognizing or generating) a rule. They are optional, but even
multiple of them can be defined and registered at the same time to the
same :class:`grammarinator.runtime.Generator`.
Registration can happen with the ``--listener`` argument of the
:ref:`grammarinator-generate<grammarinator-generate>` script or through the
constructor of :class:`grammarinator.runtime.Generator`.
When generating a rule, the :class:`grammarinator.runtime.Generator` will look
up all the registered listeners and will call the ``enter_rule`` and
``exit_rule`` methods of them. ``enter_rule`` methods will be called in the
order of the registration of the corresponding listeners, while ``exit_rule``
methods will be called in reversed order.

Grammarinator defines two listeners which can be subclassed and customized
further:

  1. :class:`grammarinator.runtime.Listener`: The subclasses can override the
     :meth:`~grammarinator.runtime.Listener.enter_rule` and the
     :meth:`~grammarinator.runtime.Listener.exit_rule` methods that take a rule
     object under construction as parameter. The methods are called for every
     rule.

  2. :class:`grammarinator.runtime.DispatchingListener`: A subclass of
     :class:`~grammarinator.runtime.Listener` that enables to write enter and
     exit methods on a per-rule basis (in the form of ``enter_ruleA`` or
     ``exit_ruleB`` for ``ruleA`` and ``ruleB``, respectively) which can make
     the listener code cleaner and more maintainable.


The following examples show how to subclass listeners.

The first example inherits from :class:`grammarinator.runtime.Listener`
and collects statistical data about the amount of generated rules. It is
inherited from :class:`grammarinator.runtime.Listener` since there is no
need to differentiate between the rules, all of them are counted, hence
the general enter and exit rules are sufficient.


.. code-block:: python
   :caption: Example implementation to subclass Listener

   from collections import defaultdict

   from grammarinator.runtime import Listener


   class StatisticsListener(Listener):
       """
       Listener to collect statistical data about the distribution of the
       generated rules.
       """

       def __init__(self):
           self.stat = defaultdict(int)

       def enter_rule(self, node):
           self.stat[node.name] += 1


The second example inherits from
:class:`grammarinator.runtime.DispatchingListener`. It only follows the enters
and exits of a hypothetical ``function`` rule to keep track of the current
nesting level.


.. code-block:: python
   :caption: Example implementation to subclass DispatchingListener

   from grammarinator.runtime import DispatchingListener


   class FunctionListener(DispatchingListener):
       """
       Listener to keep track of the nesting level of inline functions.
       """

       def __init__(self):
           self.func_depth = 0

       def enter_function(self, node):
           self.func_depth += 1

       def exit_function(self, node):
           self.func_depth -= 1


The same can be implemented with subclassing
:class:`grammarinator.runtime.Listener` of course, except that the name of the
node has to be inspected before incrementing the ``func_depth`` counter.


.. code-block:: python
   :caption: The previous example with Listener

   from grammarinator.runtime import Listener


   class FunctionListener(Listener):
       """
       Listener to keep track of the nesting level of inline functions.
       """

       def __init__(self):
           self.func_depth = 0

       def enter_rule(self, node):
            if node.name == 'function':
                self.func_depth += 1

       def exit_rule(self, node):
           if node.name == 'function':
                self.func_depth -= 1


Also see the documentation for details on `listeners in ANTLRv4`_.

.. _`listeners in ANTLRv4`: https://github.com/antlr/antlr4/blob/master/doc/listeners.md
