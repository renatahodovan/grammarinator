# Copyright (c) 2017-2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from os.path import dirname, join
from setuptools import find_packages, setup

with open(join(dirname(__file__), 'grammarinator/VERSION'), 'rb') as f:
    version = f.read().decode('ascii').strip()


setup(
    name='grammarinator',
    version=version,
    packages=find_packages(),
    url='https://github.com/renatahodovan/grammarinator',
    license='BSD',
    author='Renata Hodovan, Akos Kiss',
    author_email='hodovan@inf.u-szeged.hu, akiss@inf.u-szeged.hu',
    description='Grammarinator: Grammar-based Random Test Generator',
    long_description=open('README.rst').read(),
    install_requires=['antlerinator==4.7.1', 'autopep8'],
    zip_safe=False,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'grammarinator-process = grammarinator.process:execute',
            'grammarinator-generate = grammarinator.generate:execute',
            'grammarinator-parse = grammarinator.parse:execute',
        ]
    },
)
