"""Sphinx configuration for uncoiled documentation."""

project = "uncoiled"
copyright = "2026, Jonathan Sharpe"  # noqa: A001
author = "Jonathan Sharpe"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx_copybutton",
]

html_theme = "furo"
html_title = "uncoiled"

autodoc_member_order = "bysource"
autodoc_typehints = "description"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

exclude_patterns = ["_build"]
