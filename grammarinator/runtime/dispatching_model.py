# Copyright (c) 2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .default_model import DefaultModel


class DispatchingModel(DefaultModel):

    def choice(self, node, idx, choices):
        name = 'choice_' + node.name
        return (getattr(self, name) if hasattr(self, name) else super().choice)(node, idx, choices)

    def quantify(self, node, idx, min, max):
        name = 'quantify_' + node.name
        yield from (getattr(self, name) if hasattr(self, name) else super().quantify)(node, idx, min, max)

    def charset(self, node, idx, chars):
        name = 'charset_' + node.name
        return (getattr(self, name) if hasattr(self, name) else super().charset)(node, idx, chars)
