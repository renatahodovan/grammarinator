# Copyright (c) 2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import pickle

from ..runtime import RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantified, UnparserRuleQuantifier


class TreeCodec:
    """
    Abstract base class of tree codecs that convert between trees and bytes.
    """

    def encode(self, root):
        """
        Encode a tree into an array of bytes.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule root: Root of the tree to be encoded.
        :return: The encoded form of the tree.
        :rtype: bytes
        """
        raise NotImplementedError()

    def decode(self, data):
        """
        Decode a tree from an array of bytes.

        Raises :exc:`NotImplementedError` by default.

        :param bytes data: The encoded form of a tree.
        :return: Root of the decoded tree.
        :rtype: ~grammarinator.runtime.Rule
        """
        raise NotImplementedError()


class AnnotatedTreeCodec(TreeCodec):
    """
    Abstract base class of tree codecs that can encode and decode extra data
    (i.e., annotations) when converting between trees and bytes.
    """

    def encode(self, root):
        """
        Encode a tree without any annotations. Equivalent to calling
        :meth:`encode_annotated` with ``annotations=None``.
        """
        return self.encode_annotated(root, None)

    def encode_annotated(self, root, annotations):
        """
        Encode a tree and associated annotations into an array of bytes.

        Raises :exc:`NotImplementedError` by default.

        :param ~grammarinator.runtime.Rule root: Root of the tree to be encoded.
        :param object annotations: Data to be encoded along the tree. No
            assumption should be made about the structure or the contents of the
            data, it should be treated as opaque.
        :return: The encoded form of the tree and its annotations.
        :rtype: bytes
        """
        raise NotImplementedError()

    def decode(self, data):
        """
        Decode only the tree from an array of bytes without the associated
        annotations. Equivalent to calling :meth:`decode_annotated` and keeping
        only the first element of the returned tuple.
        """
        root, _ = self.decode_annotated(data)
        return root

    def decode_annotated(self, data):
        """
        Decode a tree and associated annotations from an array of bytes.

        Raises :exc:`NotImplementedError` by default.

        :param bytes data: The encoded form of a tree and its annotations.
        :return: Root of the decoded tree, and the decoded annotations.
        :rtype: tuple[~grammarinator.runtime.Rule,object]
        """
        raise NotImplementedError()


class PickleTreeCodec(AnnotatedTreeCodec):
    """
    Tree codec based on Python's :mod:`pickle` module.
    """

    def encode_annotated(self, root, annotations):
        return pickle.dumps((root, annotations))

    def decode_annotated(self, data):
        try:
            root, annotations = pickle.loads(data)
            return root, annotations
        except pickle.UnpicklingError:
            return None, None


class JsonTreeCodec(TreeCodec):
    """
    JSON-based tree codec.
    """

    def __init__(self, encoding='utf-8'):
        """
        :param str encoding: The encoding to use when converting between
            json-formatted text and bytes (default: utf-8).
        """
        self._encoding = encoding

    def encode(self, root):
        def _rule_to_dict(node):
            if isinstance(node, UnlexerRule):
                return {'t': 'l', 'n': node.name, 's': node.src, 'z': [node.size.depth, node.size.tokens]}
            if isinstance(node, UnparserRule):
                return {'t': 'p', 'n': node.name, 'c': node.children}
            if isinstance(node, UnparserRuleAlternative):
                return {'t': 'a', 'ai': node.alt_idx, 'i': node.idx, 'c': node.children}
            if isinstance(node, UnparserRuleQuantified):
                return {'t': 'qd', 'c': node.children}
            if isinstance(node, UnparserRuleQuantifier):
                return {'t': 'q', 'i': node.idx, 'b': node.start, 'e': node.stop, 'c': node.children}
            raise AssertionError
        return json.dumps(root, default=_rule_to_dict).encode(encoding=self._encoding)

    def decode(self, data):
        def _dict_to_rule(dct):
            if dct['t'] == 'l':
                return UnlexerRule(name=dct['n'], src=dct['s'], size=RuleSize(depth=dct['z'][0], tokens=dct['z'][1]))
            if dct['t'] == 'p':
                return UnparserRule(name=dct['n'], children=dct['c'])
            if dct['t'] == 'a':
                return UnparserRuleAlternative(alt_idx=dct['ai'], idx=dct['i'], children=dct['c'])
            if dct['t'] == 'qd':
                return UnparserRuleQuantified(children=dct['c'])
            if dct['t'] == 'q':
                return UnparserRuleQuantifier(idx=dict['i'], start=dct['b'], stop=dct['e'], children=dct['c'])
            raise json.JSONDecodeError

        try:
            return json.loads(data.decode(encoding=self._encoding), object_hook=_dict_to_rule)
        except json.JSONDecodeError:
            return None
