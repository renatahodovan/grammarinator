# Copyright (c) 2017-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from setuptools import find_packages, setup


def grammarinator_version():
    def _version_scheme(version):
        return version.format_with('{tag}')

    def _local_scheme(version):
        if version.exact and not version.dirty:
            return ''
        parts = ['{distance}'.format(distance=version.distance)]
        if version.node:
            parts.append('{node}'.format(node=version.node))
        if version.dirty:
            parts.append('d{time:%Y%m%d}'.format(time=version.time))
        return '+{parts}'.format(parts='.'.join(parts))

    return { 'version_scheme': _version_scheme, 'local_scheme': _local_scheme }


setup(
    name='grammarinator',
    packages=find_packages(),
    url='https://github.com/renatahodovan/grammarinator',
    license='BSD',
    author='Renata Hodovan, Akos Kiss',
    author_email='hodovan@inf.u-szeged.hu, akiss@inf.u-szeged.hu',
    description='Grammarinator: Grammar-based Random Test Generator',
    long_description=open('README.rst').read(),
    install_requires=['antlerinator==4.8', 'autopep8', 'jinja2', 'setuptools'],
    zip_safe=False,
    include_package_data=True,
    setup_requires=['setuptools_scm'],
    use_scm_version=grammarinator_version,
    entry_points={
        'console_scripts': [
            'grammarinator-process = grammarinator.process:execute',
            'grammarinator-generate = grammarinator.generate:execute',
            'grammarinator-parse = grammarinator.parse:execute',
        ]
    },
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Code Generators',
        'Topic :: Software Development :: Testing',
    ],
)
