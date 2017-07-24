# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import pkgutil

import antlerinator


__version__ = pkgutil.get_data(__package__, 'VERSION').decode('ascii').strip()
default_antlr_path = antlerinator.antlr_jar_path
