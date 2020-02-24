# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import sys

from os import listdir
from os.path import basename, commonprefix, split, splitext
from subprocess import CalledProcessError, PIPE, Popen

from antlr4 import error

logger = logging.getLogger(__name__)


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


def build_grammars(in_files, out, antlr):
    """
    Build lexer and grammar from ANTLRv4 grammar files in Python3 target.

    :param in_files: List resources (grammars and additional sources) needed to parse the input.
    :param out: Directory where grammars are placed and where the output will be generated to.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :return: List of references/names of the lexer, parser and listener classes of the target.
    """
    try:
        # TODO: support Java parsers too.
        languages = {
            'python': {'antlr_arg': '-Dlanguage=Python3',
                       'ext': 'py',
                       'listener_format': 'Listener'}
        }

        grammars = tuple(fn for fn in in_files if fn.endswith('.g4'))

        # Generate parser and lexer in the target language and return either with
        # python class ref or the name of java classes.
        cmd = 'java -jar {antlr} {lang} {grammars}'.format(antlr=antlr,
                                                           lang=languages['python']['antlr_arg'],
                                                           grammars=' '.join(grammars))

        with Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True, cwd=out) as proc:
            stdout, stderr = proc.communicate()
            if proc.returncode:
                logger.error('Building grammars %r failed!\n%s\n%s\n', grammars,
                             stdout.decode('utf-8', 'ignore'),
                             stderr.decode('utf-8', 'ignore'))
                raise CalledProcessError(returncode=proc.returncode, cmd=cmd, output=stdout + stderr)

        files = set(listdir(out)) - set(in_files)
        filename = basename(grammars[0])

        def file_endswith(end_pattern):
            return splitext(split(list(
                filter(lambda x: len(commonprefix([filename, x])) > 0 and x.endswith(end_pattern), files))[0])[1])[0]

        # Extract the name of lexer and parser from their path.
        lexer = file_endswith('Lexer.{ext}'.format(ext=languages['python']['ext']))
        parser = file_endswith('Parser.{ext}'.format(ext=languages['python']['ext']))
        # The name of the generated listeners differs if Python or other language target is used.
        listener = file_endswith('{listener_format}.{ext}'.format(listener_format=languages['python']['listener_format'], ext=languages['python']['ext']))

        # Add the path of the built lexer and parser to the Python path to be available for importing.
        if out not in sys.path:
            sys.path.append(out)

        return (getattr(__import__(x, globals(), locals(), [x], 0), x) for x in [lexer, parser, listener])
    except Exception as e:
        logger.error('Exception while loading parser modules', exc_info=e)
        raise e
