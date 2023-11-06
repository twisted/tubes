# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
from pprint import pprint
import subprocess

project = "Tubes"
copyright = "2023, Glyph"
author = "Glyph"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.intersphinx",
    "pydoctor.sphinx_ext.build_apidocs",
]

import pathlib

_project_root = pathlib.Path(__file__).parent.parent

# -- Extension configuration ----------------------------------------------
_git_reference = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    text=True,
    encoding="utf8",
    capture_output=True,
    check=True,
).stdout


print(f"== Environment dump for {_git_reference} ===")
pprint(dict(os.environ))
print("======")


# Try to find URL fragment for the GitHub source page based on current
# branch or tag.

if _git_reference == "HEAD":
    # It looks like the branch has no name.
    # Fallback to commit ID.
    _git_reference = subprocess.getoutput("git rev-parse HEAD")

if os.environ.get("READTHEDOCS", "") == "True":
    rtd_version = os.environ.get("READTHEDOCS_VERSION", "")
    if "." in rtd_version:
        # It looks like we have a tag build.
        _git_reference = rtd_version

_source_root = _project_root

pydoctor_args = [
    # pydoctor should not fail the sphinx build, we have another tox environment for that.
    "--intersphinx=https://docs.twisted.org/en/twisted-22.1.0/api/objects.inv",
    "--intersphinx=https://docs.python.org/3/objects.inv",
    "--intersphinx=https://zopeinterface.readthedocs.io/en/latest/objects.inv",
    # TODO: not sure why I have to specify these all twice.

    f"--config={_project_root}/.pydoctor.cfg",
    f"--html-viewsource-base=https://github.com/glyph/tubes/tree/{_git_reference}",
    f"--project-base-dir={_source_root}",
    "--html-output={outdir}/api",
    "--privacy=HIDDEN:tubes.test.*",
    "--privacy=HIDDEN:tubes.test",
    "--privacy=HIDDEN:**.__post_init__",
    str(_source_root / "tubes"),
]
pydoctor_url_path = "/en/{rtd_version}/api/"
intersphinx_mapping = {
    "py3": ("https://docs.python.org/3", None),
    "zopeinterface": ("https://zopeinterface.readthedocs.io/en/latest", None),
    "twisted": ("https://docs.twisted.org/en/twisted-22.1.0/api", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "alabaster"
htmlhelp_basename = "Tubesdoc"
