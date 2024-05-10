# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Grammarinator'
author = 'Renata Hodovan, Akos Kiss'
copyright = '2017-2024, %s' % author

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
from grammarinator import __version__ as version
# The full version, including alpha/beta/rc tags.
release = version


# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinxcontrib.runcmd',
]

# templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# on_rtd is whether we are on readthedocs.org
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'

if not on_rtd:  # only import and set the theme if we're building docs locally
    import sphinx_rtd_theme
    html_theme = 'sphinx_rtd_theme'
    html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

# The name for this set of Sphinx documents.
# "<project> v<release> documentation" by default.
#
html_title = '%s %s documentation' % (project, release)

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# If true, links to the reST sources are added to the pages.
#
html_show_sourcelink = False

# If true, navigation will be scrolled with the main page and navigation
# groups won't be closed when selecting an item.
sticky_navigation = True


# -- Extension configuration -------------------------------------------------

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'fuzzinator': ('https://fuzzinator.readthedocs.io/en/latest', None),
}

autoclass_content = 'both'
autodoc_inherit_docstrings = False
