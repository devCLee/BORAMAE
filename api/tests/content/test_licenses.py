"""content/licenses.json: the license inventory of every data and code source (TR-O-004).

The Methods page renders one attribution per entry, so an entry missing here is also
missing from the page.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

from boramae.services.content import CONTENT_FILES, read_content

ROOT = Path(__file__).parents[3]
CONTENT = ROOT / "content"
ENTRIES = read_content(
    CONTENT / CONTENT_FILES["licenses"][0], CONTENT_FILES["licenses"][1]
)
REGISTRY = read_content(
    CONTENT / CONTENT_FILES["registry"][0], CONTENT_FILES["registry"][1]
)
NAMES = {entry.name.lower() for entry in ENTRIES}
URLS = {entry.url for entry in ENTRIES}
WEB_PACKAGES = sorted(
    json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))[
        "dependencies"
    ]
)
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9_.\-]+")
API_PACKAGES = [
    PACKAGE_NAME.match(requirement).group(0)
    for requirement in tomllib.loads(
        (ROOT / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["dependencies"]
]
REGISTRY_DOIS = sorted({link.doi for link in REGISTRY if link.doi})
DOI_BASE = "https://doi.org/"
# The data that the build reads or bundles: POWER and its source reanalysis, and the
# Natural Earth outlines of the base map and the gazetteer, through world-atlas.
DATA_SOURCES = ["NASA POWER", "MERRA-2", "Natural Earth", "world-atlas"]
TEXT_FIELDS = ["name", "license", "url", "citation"]
# A Creative Commons NC term (BY-NC, BY-NC-SA, BY-NC-ND) or the words themselves.
NON_COMMERCIAL = re.compile(r"\bNC\b|non-?commercial", re.IGNORECASE)


def _name(entry):
    return entry.name


@pytest.mark.parametrize("field", TEXT_FIELDS)
@pytest.mark.parametrize("entry", ENTRIES, ids=_name)
def test_entry_fills_text_field(entry, field):
    assert getattr(entry, field).strip()


@pytest.mark.parametrize("entry", ENTRIES, ids=_name)
def test_entry_license_is_not_non_commercial(entry):
    assert NON_COMMERCIAL.search(entry.license) is None


@pytest.mark.parametrize("package", WEB_PACKAGES + API_PACKAGES)
def test_runtime_package_has_entry(package):
    assert package.lower() in NAMES


@pytest.mark.parametrize("doi", REGISTRY_DOIS)
def test_registry_source_has_entry_by_doi(doi):
    assert DOI_BASE + doi in URLS


@pytest.mark.parametrize("name", DATA_SOURCES)
def test_data_source_has_entry(name):
    assert name.lower() in NAMES
