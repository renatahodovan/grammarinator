# Copyright (c) 2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import os
import pytest

from run_grammars import collect_grammar_commands, run_grammar


grammars_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples', 'grammars')


@pytest.mark.parametrize('grammar, commands', collect_grammar_commands(grammars_dir))
def test_grammar(grammar, commands, tmpdir):
    run_grammar(grammar, commands, str(tmpdir))
