project = "Synthetix"
copyright = "2023, Synthetix DAO"
author = "Synthetix DAO"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx_rtd_theme",
]
autosummary_generate = True

templates_path = ["_templates"]

exclude_patterns = [
    ".DS_Store",
    "deployments/*",
]

source_suffix = [".rst", ".md"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
