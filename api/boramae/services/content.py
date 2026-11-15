"""Load a content file by name, validated against its model (DES-014)."""

from functools import cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from boramae.config import load_settings
from boramae.contracts.content import (
    Board,
    CatalogInputs,
    CatalogSeed,
    Chip,
    DemoCase,
    KeywordEntry,
    LicenseEntry,
    Place,
    RegistryLink,
)

# Name -> path under the content folder and the model of the whole file.
CONTENT_FILES: dict[str, tuple[str, Any]] = {
    "catalog_seed": ("catalog.seed.json", CatalogSeed),
    "inputs": ("catalog-inputs.json", CatalogInputs),
    "registry": ("registry.json", list[RegistryLink]),
    "boards": ("boards.json", list[Board]),
    "keywords": ("keywords.json", list[KeywordEntry]),
    "gazetteer": ("gazetteer.json", list[Place]),
    "chips": ("chips.json", list[Chip]),
    "licenses": ("licenses.json", list[LicenseEntry]),
    "demo_cases": ("demo/cases.json", list[DemoCase]),
}


def content_dir() -> Path:
    return Path(load_settings().content_dir)


def read_content(path: Path, model: Any) -> Any:
    """Return the file validated against the model; raises ValidationError."""
    return TypeAdapter(model).validate_json(path.read_bytes())


@cache
def load_content(name: str) -> Any:
    """Return the validated content file of a CONTENT_FILES name, read once."""
    relative, model = CONTENT_FILES[name]
    return read_content(content_dir() / relative, model)
