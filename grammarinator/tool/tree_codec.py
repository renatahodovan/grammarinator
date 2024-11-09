# Copyright (c) 2023-2024 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import pickle
import struct

from math import inf

import flatbuffers

from ..runtime import RuleSize, UnlexerRule, UnparserRule, UnparserRuleAlternative, UnparserRuleQuantified, UnparserRuleQuantifier
from .fbs import CreateFBRuleSize, FBRule, FBRuleAddAltIdx, FBRuleAddChildren, FBRuleAddIdx, FBRuleAddImmutable, FBRuleAddName, FBRuleAddSize, FBRuleAddSrc, FBRuleAddStart, FBRuleAddStop, FBRuleAddType, FBRuleEnd, FBRuleStart, FBRuleStartChildrenVector, FBRuleType


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

    def __init__(self, encoding='utf-8', encoding_errors='surrogatepass'):
        """
        :param str encoding: The encoding to use when converting between
            json-formatted text and bytes (default: utf-8).
        """
        self._encoding = encoding
        self._encoding_errors = encoding_errors

    def encode(self, root):
        def _rule_to_dict(node):
            if isinstance(node, UnlexerRule):
                return {'t': 'l', 'n': node.name, 's': node.src, 'z': [node.size.depth, node.size.tokens], 'i': node.immutable}
            if isinstance(node, UnparserRule):
                return {'t': 'p', 'n': node.name, 'c': node.children}
            if isinstance(node, UnparserRuleAlternative):
                return {'t': 'a', 'ai': node.alt_idx, 'i': node.idx, 'c': node.children}
            if isinstance(node, UnparserRuleQuantified):
                return {'t': 'qd', 'c': node.children}
            if isinstance(node, UnparserRuleQuantifier):
                return {'t': 'q', 'i': node.idx, 'b': node.start, 'e': node.stop if node.stop != inf else -1, 'c': node.children}
            raise AssertionError
        return json.dumps(root, default=_rule_to_dict).encode(encoding=self._encoding, errors=self._encoding_errors)

    def decode(self, data):
        def _dict_to_rule(dct):
            if dct['t'] == 'l':
                return UnlexerRule(name=dct['n'], src=dct['s'], size=RuleSize(depth=dct['z'][0], tokens=dct['z'][1]), immutable=dct['i'])
            if dct['t'] == 'p':
                return UnparserRule(name=dct['n'], children=dct['c'])
            if dct['t'] == 'a':
                return UnparserRuleAlternative(alt_idx=dct['ai'], idx=dct['i'], children=dct['c'])
            if dct['t'] == 'qd':
                return UnparserRuleQuantified(children=dct['c'])
            if dct['t'] == 'q':
                return UnparserRuleQuantifier(idx=dct['i'], start=dct['b'], stop=dct['e'] if dct['e'] != -1 else inf, children=dct['c'])
            raise json.JSONDecodeError

        try:
            return json.loads(data.decode(encoding=self._encoding, errors=self._encoding_errors), object_hook=_dict_to_rule)
        except json.JSONDecodeError:
            return None


class FlatBuffersTreeCodec(TreeCodec):
    """
    FlatBuffers-based tree codec.
    """

    def __init__(self, encoding='utf-8', encoding_errors='surrogatepass'):
        """
        :param str encoding: The encoding to use when converting between
            flatbuffers-encoded text and bytes (default: utf-8).
        """
        self._encoding = encoding
        self._encoding_errors = encoding_errors

    def encode(self, root):
        def buildFBRule(rule):
            if isinstance(rule, UnlexerRule):
                fb_name = builder.CreateString(rule.name, encoding=self._encoding, errors=self._encoding_errors)
                fb_src = builder.CreateString(rule.src, encoding=self._encoding, errors=self._encoding_errors)
                FBRuleStart(builder)
                FBRuleAddType(builder, FBRuleType.UnlexerRuleType)
                FBRuleAddName(builder, fb_name)
                FBRuleAddSrc(builder, fb_src)
                FBRuleAddSize(builder, CreateFBRuleSize(builder, rule.size.depth, rule.size.tokens))
                FBRuleAddImmutable(builder, rule.immutable)
            else:
                children = [buildFBRule(child) for child in rule.children]
                FBRuleStartChildrenVector(builder, len(children))
                for fb_child in reversed(children):
                    builder.PrependUOffsetTRelative(fb_child)
                fb_children = builder.EndVector()
                if isinstance(rule, UnparserRule):
                    fb_name = builder.CreateString(rule.name, encoding=self._encoding, errors=self._encoding_errors)
                FBRuleStart(builder)
                FBRuleAddChildren(builder, fb_children)
                if isinstance(rule, UnparserRule):
                    FBRuleAddName(builder, fb_name)
                    FBRuleAddType(builder, FBRuleType.UnparserRuleType)
                elif isinstance(rule, UnparserRuleQuantifier):
                    FBRuleAddType(builder, FBRuleType.UnparserRuleQuantifierType)
                    FBRuleAddIdx(builder, rule.idx)
                    FBRuleAddStart(builder, rule.start)
                    FBRuleAddStop(builder, rule.stop if rule.stop != inf else -1)
                elif isinstance(rule, UnparserRuleQuantified):
                    FBRuleAddType(builder, FBRuleType.UnparserRuleQuantifiedType)
                elif isinstance(rule, UnparserRuleAlternative):
                    FBRuleAddType(builder, FBRuleType.UnparserRuleAlternativeType)
                    FBRuleAddAltIdx(builder, rule.alt_idx)
                    FBRuleAddIdx(builder, rule.idx)
            return FBRuleEnd(builder)

        builder = flatbuffers.Builder()
        builder.Finish(buildFBRule(root))
        return bytes(builder.Output())

    def decode(self, data):
        def readFBRule(fb_rule):
            rule_type = fb_rule.Type()
            if rule_type == FBRuleType.UnlexerRuleType:
                fb_size = fb_rule.Size()
                rule = UnlexerRule(name=fb_rule.Name().decode(self._encoding, self._encoding_errors),
                                   src=fb_rule.Src().decode(self._encoding, self._encoding_errors),
                                   size=RuleSize(depth=fb_size.Depth(), tokens=fb_size.Tokens()),
                                   immutable=fb_rule.Immutable())
            else:
                children = [readFBRule(fb_rule.Children(i)) for i in range(fb_rule.ChildrenLength())]
                if rule_type == FBRuleType.UnparserRuleType:
                    rule = UnparserRule(name=fb_rule.Name().decode(self._encoding, self._encoding_errors), children=children)
                elif rule_type == FBRuleType.UnparserRuleQuantifierType:
                    stop = fb_rule.Stop()
                    rule = UnparserRuleQuantifier(idx=fb_rule.Idx(), start=fb_rule.Start(), stop=stop if stop != -1 else inf, children=children)
                elif rule_type == FBRuleType.UnparserRuleQuantifiedType:
                    rule = UnparserRuleQuantified(children=children)
                elif rule_type == FBRuleType.UnparserRuleAlternativeType:
                    rule = UnparserRuleAlternative(alt_idx=fb_rule.AltIdx(), idx=fb_rule.Idx(), children=children)
                else:
                    assert False, f'Unexpected type {rule_type}'
            return rule

        try:
            return readFBRule(FBRule.GetRootAs(bytearray(data)))
        except struct.error:
            return None
