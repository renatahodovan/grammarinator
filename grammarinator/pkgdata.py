# Copyright (c) 2017-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import antlerinator
import pkg_resources


__version__ = pkg_resources.get_distribution(__package__).version
default_antlr_path = antlerinator.antlr_jar_path
