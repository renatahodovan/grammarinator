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

       primitive : String | (Decimal | Float) | Bool ;
       String : [a-zA-Z] ;
       Decimal : [0-9]+;
       Float : '0'? '.' [0-9]+ ;
       Bool : 'true' | 'false' ;

    .. code-block:: python
       :caption: Example subclassing of DefaultModel

       class PrimitiveModel(DefaultModel):

           def choice(self, node, idx, weights):
               # Increase the probability of generating numeric values
               # (decimal and float), i.e., choosing the second alternative.
               if node.name == 'primitive' and idx == 1:
                   weights[1] *= 5
               return super().choice(node, idx, weights)

           def quantify(self, node, idx, cnt, start, stop):
               if node.name == 'Float' and idx == 1:
                   # Generate floats with two decimal digits at least.
                   start = 2
               return super().quantify(node, idx, cnt, start, stop)

           def charset(self, node, idx, chars):
               # Ensure not choosing `0` as the first digit of a decimal.
               if node.name == 'Decimal' and len(node.src) == 0:
                   chars = tuple(c for c in chars if c != '0')
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
               return super(DispatchingModel, self).choice(node, idx, weights)

           def quantify_Float(self, node, idx, cnt, start, stop):
               if idx == 1:
                   # Generate floats with two decimal digits at least.
                   start = 2
               return super(DispatchingModel, self).quantify(node, idx, cnt, start, stop)

           def charset_Decimal(self, node, idx, chars):
               # Ensure not choosing `0` as the first digit of a decimal.
               if len(node.src) == 0:
                   chars = tuple(c for c in chars if c != '0')
               return super(DispatchingModel, self).charset(node, idx, chars)

  3. :class:`grammarinator.runtime.WeightedModel`: This model modifies the
     behavior of another model by adjusting (pre-multiplying) the weights of
     alternatives and by setting the probability of repeating a quantified
     subexpression. By default, the multiplier of each alternative starts from
     1 and the probability of each quantifier is 0.5, unless custom values are
     assigned to specific alternatives or quantifiers. This assignment can
     happen through the constructor of WeightedModel (when using the API) or
     with the ``--weigths`` CLI option of the
     :ref:`grammarinator-generate<grammarinator-generate>` utility by providing
     a file containing the weights.

     The expected format of the weights differs depending on whether
     Grammarinator is used from API or from CLI. When using the API, a compact
     representation is used, which is not JSON serializable. For API usage,
     refer to the documention of :class:`grammarinator.runtime.WeightedModel`.
     When providing weights from the CLI, then the input JSON file should have
     the following format:

    .. code-block:: text

      {
        "alts": { "ruleName_A": {"alternation_B_idx": {"alternative_C_idx": weight_ABC, ...}, ...}, ... ,
        "quants": { "ruleName_C": {"quant_D_idx": weight_ABC, ...}, ... ,
      }
