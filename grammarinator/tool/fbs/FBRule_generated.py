# automatically generated by the FlatBuffers compiler, do not modify

# namespace: fbs

import flatbuffers
from flatbuffers.compat import import_numpy
np = import_numpy()

class FBRuleType(object):
    UnlexerRuleType = 0
    UnparserRuleType = 1
    UnparserRuleQuantifierType = 2
    UnparserRuleQuantifiedType = 3
    UnparserRuleAlternativeType = 4


class FBRuleSize(object):
    __slots__ = ['_tab']

    @classmethod
    def SizeOf(cls):
        return 8

    # FBRuleSize
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # FBRuleSize
    def Depth(self): return self._tab.Get(flatbuffers.number_types.Int32Flags, self._tab.Pos + flatbuffers.number_types.UOffsetTFlags.py_type(0))
    # FBRuleSize
    def Tokens(self): return self._tab.Get(flatbuffers.number_types.Int32Flags, self._tab.Pos + flatbuffers.number_types.UOffsetTFlags.py_type(4))

def CreateFBRuleSize(builder, depth, tokens):
    builder.Prep(4, 8)
    builder.PrependInt32(tokens)
    builder.PrependInt32(depth)
    return builder.Offset()


class FBRule(object):
    __slots__ = ['_tab']

    @classmethod
    def GetRootAs(cls, buf, offset=0):
        n = flatbuffers.encode.Get(flatbuffers.packer.uoffset, buf, offset)
        x = FBRule()
        x.Init(buf, n + offset)
        return x

    @classmethod
    def GetRootAsFBRule(cls, buf, offset=0):
        """This method is deprecated. Please switch to GetRootAs."""
        return cls.GetRootAs(buf, offset)
    # FBRule
    def Init(self, buf, pos):
        self._tab = flatbuffers.table.Table(buf, pos)

    # FBRule
    def Type(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(4))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int8Flags, o + self._tab.Pos)
        return 0

    # FBRule
    def Name(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(6))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # FBRule
    def Children(self, j):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            x = self._tab.Vector(o)
            x += flatbuffers.number_types.UOffsetTFlags.py_type(j) * 4
            x = self._tab.Indirect(x)
            obj = FBRule()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None

    # FBRule
    def ChildrenLength(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        if o != 0:
            return self._tab.VectorLen(o)
        return 0

    # FBRule
    def ChildrenIsNone(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(8))
        return o == 0

    # FBRule
    def Src(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(10))
        if o != 0:
            return self._tab.String(o + self._tab.Pos)
        return None

    # FBRule
    def Size(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(12))
        if o != 0:
            x = o + self._tab.Pos
            obj = FBRuleSize()
            obj.Init(self._tab.Bytes, x)
            return obj
        return None

    # FBRule
    def Idx(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(14))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # FBRule
    def Start(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(16))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # FBRule
    def Stop(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(18))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # FBRule
    def AltIdx(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(20))
        if o != 0:
            return self._tab.Get(flatbuffers.number_types.Int32Flags, o + self._tab.Pos)
        return 0

    # FBRule
    def Immutable(self):
        o = flatbuffers.number_types.UOffsetTFlags.py_type(self._tab.Offset(22))
        if o != 0:
            return bool(self._tab.Get(flatbuffers.number_types.BoolFlags, o + self._tab.Pos))
        return False

def FBRuleStart(builder):
    builder.StartObject(10)

def FBRuleAddType(builder, type):
    builder.PrependInt8Slot(0, type, 0)

def FBRuleAddName(builder, name):
    builder.PrependUOffsetTRelativeSlot(1, flatbuffers.number_types.UOffsetTFlags.py_type(name), 0)

def FBRuleAddChildren(builder, children):
    builder.PrependUOffsetTRelativeSlot(2, flatbuffers.number_types.UOffsetTFlags.py_type(children), 0)

def FBRuleStartChildrenVector(builder, numElems):
    return builder.StartVector(4, numElems, 4)

def FBRuleAddSrc(builder, src):
    builder.PrependUOffsetTRelativeSlot(3, flatbuffers.number_types.UOffsetTFlags.py_type(src), 0)

def FBRuleAddSize(builder, size):
    builder.PrependStructSlot(4, flatbuffers.number_types.UOffsetTFlags.py_type(size), 0)

def FBRuleAddIdx(builder, idx):
    builder.PrependInt32Slot(5, idx, 0)

def FBRuleAddStart(builder, start):
    builder.PrependInt32Slot(6, start, 0)

def FBRuleAddStop(builder, stop):
    builder.PrependInt32Slot(7, stop, 0)

def FBRuleAddAltIdx(builder, altIdx):
    builder.PrependInt32Slot(8, altIdx, 0)

def FBRuleAddImmutable(builder, immutable):
    builder.PrependBoolSlot(9, immutable, 0)

def FBRuleEnd(builder):
    return builder.EndObject()



