======
Models
======

Models in Grammarinator are responsible for making decisions at each branching
point while generating test cases. These decisions include selecting an
alternative from a set of options, quantifying a subrule, or choosing a
character from a character set. By using models, the generation process can
be guided while keeping the source grammar clean and separate from the
decision-making logic. (Another way of guiding the selection of alternatives
is by injecting :ref:`semantic predicates <semantic-predicates>` into the
grammar.)
A model can be registered with using the ``--model`` argument in the
:ref:`grammarinator-generate<grammarinator-generate>` script or through the
constructor of :class:`grammarinator.runtime.Generator`. If no custom model
is specified, the default model (:class:`grammarinator.runtime.DefaultModel`)
will be used.

Grammarinator provides three built-in models, each of which is inherited from
the :class:`grammarinator.runtime.Model` class. The models can be subclassed
and further customized according to specific requirements. The built-in
models are:

  1. :class:`grammarinator.runtime.DefaultModel`: This model provides a default
     implementation for three key functionalities:

     a) **Alternative selection**: The
        :meth:`grammarinator.runtime.DefaultModel.choice` method chooses an
        alternative based on their assigned weights. The weights are normalized
        so that their sum is 1, and then they are treated as probabilities.
     b) **Subrule quantification**: The
        :meth:`grammarinator.runtime.DefaultModel.quantify` method generates
        the minimum required amount of subrules and then decides iteratively
        whether to generate one more item or terminate quantification. It is
        implemented as a :term:`generator` method.
     c) **Character selection from a charset**: The
        :meth:`grammarinator.runtime.DefaultModel.charset` method randomly
        selects characters from the options with uniform distribution.

    .. code-block:: antlr
       :caption: Example grammar to represent the usage of DefaultModel

       grammar Primitives;

       primitive : string | (decimal | float) | bool ;
       string : [a-zA-Z] ;
       decimal : [0-9]+;
       float : '0'? '.' [0-9]+ ;
       bool : 'true' | 'false' ;

    .. code-block:: python
       :caption: Example subclassing of DefaultModel

       class PrimitiveModel(DefaultModel):

           def choice(self, node, idx, weights):
               # Increase the probability of generating numeric values
               # (decimal and float), i.e., choosing the second alternative.
               if node.name == 'primitive' and idx == 1:
                   weights[1] *= 5
               return super().choice(node, idx, weights)

          def quantify(self, node, idx, min, max):
              if node.name == 'float' and idx == 1:
                  # Generate floats with two decimal digits at least.
                  min = 2
              yield from super().quantify(node, idx, min, max)

          def charset(self, node, idx, chars):
              # Ensure not choosing `0` as the first digit of a decimal.
              if node.name == 'decimal' and len(node.children) == 0:
                  non_zero_chars = chars[:]
                  non_zero_chars.remove('0')
                  return super().charset(node, idx, non_zero_chars)
              return super().charset(node, idx, chars)


  2. :class:`grammarinator.runtime.DispatchingModel`: This model is a
     specialized version of :class:`grammarinator.runtime.DefaultModel` that
     allows overriding the default behavior for specific rules. It enables the
     creation of separate methods for each rule, such as ``choice_<ruleName>``,
     ``quantify_<ruleName>``, and ``charset_<ruleName>``, to customize their
     behavior.

    The following example shows how the previous snippet would look like with
    :class:`grammarinator.runtime.DispatchingModel`:

    .. code-block:: python
       :caption: Example subclassing of DispatchingModel

       class PrimitiveModel(DispatchingModel):

           def choice_primitive(self, node, idx, weights):
               # Increase the probability of generating numeric values
               # (decimal and float), i.e., choosing the second alternative.
               if idx == 1:
                   weights[1] *= 5
               return super().choice(node, idx, weights)

          def quantify_float(self, node, idx, min, max):
              if idx == 1:
                  # Generate floats with two decimal digits at least.
                  min = 2
              yield from super().quantify(node, idx, min, max)

          def charset_decimal(self, node, idx, chars):
              # Ensure not choosing `0` as the first digit of a decimal.
              if len(node.children) == 0:
                  non_zero_chars = chars[:]
                  non_zero_chars.remove('0')
                  return super().charset(node, idx, non_zero_chars)
              return super().charset(node, idx, chars)

  3. :class:`grammarinator.runtime.WeightedModel`: This model modifies the
     behavior of another model by adjusting (pre-multiplying) the weights of
     alternatives. By default, the multiplier of each alternative starts from 1,
     unless custom values are assigned to specific alternatives. This assignment
     can happen through the constructor of WeightedModel (when using the API)
     or with the ``--weigths`` CLI option of the
     :ref:`grammarinator-generate<grammarinator-generate>` utility by providing
     a file containing the weights.

     The expected format of the weights differs depending on whether
     Grammarinator is used from API or from CLI. When using the API, a compact
     representation is used, which is not JSON serializable. For API usage,
     refer to the documention of :class:`grammarinator.runtime.WeightedModel`.
     When providing weights from the CLI, then the input JSON file should have
     the following format:

    .. code-block:: text

     { "ruleName_A": {"alternation_B_idx": {"alternative_C_idx": weight_ABC, ...}, ...}, ... }
