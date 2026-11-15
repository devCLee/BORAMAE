"""Check the content files against their models and against each other.

Run: python -m boramae.batch.lint_content [--only name,name]. Without --only every
listed file that exists is checked. Files that the table does not list are skipped.
Cross-checks compare only files that this run checked and found valid.
"""

import argparse
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from boramae.contracts.content import DemoAnswer, DemoScript
from boramae.services.content import CONTENT_FILES, content_dir, read_content

_SINGLE_FILES = (
    "catalog_seed",
    "inputs",
    "registry",
    "boards",
    "keywords",
    "gazetteer",
    "chips",
    "licenses",
)
# Name -> (path or glob under the content folder, model of the whole file).
LINT_TABLE: dict[str, list[tuple[str, Any]]] = {
    name: [CONTENT_FILES[name]] for name in _SINGLE_FILES
} | {
    "demo": [
        CONTENT_FILES["demo_cases"],
        ("demo/scripts/*.json", DemoScript),
        ("demo/answers/*.json", list[DemoAnswer]),
    ]
}
_SCRIPTS_PREFIX = "demo/scripts/"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lint-content", description=__doc__)
    parser.add_argument(
        "--only",
        type=_names,
        default=list(LINT_TABLE),
        help=f"comma-separated names from: {','.join(LINT_TABLE)}",
    )
    args = parser.parse_args(argv)
    valid, errors, checked = lint(content_dir(), args.only)
    errors += cross_check(valid)
    for line in errors:
        print(line)
    print(f"lint-content: {checked} files, {len(errors)} errors")
    return 1 if errors else 0


def lint(root: Path, names: list[str]) -> tuple[dict[str, Any], list[str], int]:
    """Validate each listed file; return the valid ones by path, the errors, the count."""
    valid: dict[str, Any] = {}
    errors: list[str] = []
    paths = [
        (path, model)
        for name in names
        for pattern, model in LINT_TABLE[name]
        for path in sorted(root.glob(pattern))
    ]
    for path, model in paths:
        relative = path.relative_to(root).as_posix()
        try:
            valid[relative] = read_content(path, model)
        except ValidationError as exc:
            errors += [_format(relative, error) for error in exc.errors()]
    return valid, errors, len(paths)


def cross_check(valid: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    registry, boards = valid.get("registry.json"), valid.get("boards.json")
    if registry is not None and boards is not None:
        link_ids = {link.id for link in registry}
        errors += [
            f"boards.json: {i}.{side}.{j}: unknown registry link {link_id!r}"
            for i, board in enumerate(boards)
            for side in ("drivers", "responses")
            for j, link_id in enumerate(getattr(board, side))
            if link_id not in link_ids
        ]
    inputs, chips = valid.get("catalog-inputs.json"), valid.get("chips.json")
    if inputs is not None and chips is not None:
        input_ids = {item.id for item in inputs.inputs}
        errors += [
            f"chips.json: {i}.input_id: unknown catalog input {chip.input_id}"
            for i, chip in enumerate(chips)
            if chip.input_id not in input_ids
        ]
    cases = valid.get(CONTENT_FILES["demo_cases"][0])
    if cases is not None:
        case_ids = {case.id for case in cases}
        errors += [
            f"{relative}: case_id: unknown demo case {script.case_id!r}"
            for relative, script in valid.items()
            if relative.startswith(_SCRIPTS_PREFIX) and script.case_id not in case_ids
        ]
    return errors


def _names(text: str) -> list[str]:
    names = [name.strip() for name in text.split(",") if name.strip()]
    unknown = sorted(set(names) - LINT_TABLE.keys())
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown names: {', '.join(unknown)}")
    return names


def _format(relative: str, error: Any) -> str:
    field = ".".join(str(part) for part in error["loc"]) or "<file>"
    return f"{relative}: {field}: {error['msg']}"


if __name__ == "__main__":
    sys.exit(main())
