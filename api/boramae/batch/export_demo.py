"""export-demo: the demo bundle of the web app from the stored results (Flow E, step 1).

Run: python -m boramae.batch export-demo [--out DIR] (default ../web/public/demo). Each
case of content/demo/cases.json gets its parse proposal in each language, its stored
trend, the stored board for a significant verdict or the stored scan for another
tested verdict (TRD Q-12), the trend of each board node and scan hit, and the guide
answers of content/demo/answers that exist; then the catalog and manifest.json. It
computes nothing, so run warm first. Files hold stored bytes: a second export is equal.
"""

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from boramae import deps
from boramae.batch.export_refs import hit_trends, node_trends
from boramae.batch.warm import (
    CASEBOARD_KIND,
    SCAN_KIND,
    TREND_KIND,
    Service,
    service_table,
)
from boramae.contracts.content import (
    DemoCase,
    DemoManifest,
    ManifestAnswers,
    ManifestCase,
    ManifestFile,
)
from boramae.contracts.http import CacheStatus
from boramae.contracts.results import TrendResult
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import (
    SPEC_VERSION,
    ContractModel,
    Lang,
    ParseProposal,
    RequestSpec,
    SpecMetric,
    encode_request_spec,
)
from boramae.engine.types import Verdict
from boramae.errors import ProblemError
from boramae.ports import ObjectStore, SeriesReader
from boramae.services import parse_cache
from boramae.services.catalog import CATALOG_PATH
from boramae.services.content import content_dir, load_content
from boramae.services.parser_rules import parse_rules
from boramae.spec.canonical import canonicalize, result_key
from boramae.spec.validate import validate_request
from boramae.store.pool import WorkerPool
from boramae.store.results import ResultService, result_path

DEFAULT_OUT = "../web/public/demo"
ANSWERS_FOLDER = "demo/answers"
CATALOG_FILE = "catalog.json"
MANIFEST_FILE = "manifest.json"
LANGS: tuple[Lang, ...] = ("en", "ko")
BOARD_VERDICTS = (Verdict.SignificantRise.value, Verdict.SignificantFall.value)
FAILED_EXIT_CODE = 1

Stored = Callable[[RequestSpec], tuple[bytes, str]]  # spec -> stored body and key


class ExportError(Exception):
    """The store cannot give the bundle of a demo case."""


class StoredResults(ResultService):
    """A result service that only reads: a result that is not stored is an error."""

    def __init__(self, store: ObjectStore) -> None:
        super().__init__(store, WorkerPool(1, 0.0))  # nothing computes: no slot taken

    def get_or_compute(
        self,
        kind: str,
        key: str,
        compute: Callable[[], ContractModel],
        bounded: bool = True,
    ) -> tuple[bytes, CacheStatus]:
        return self.read(kind, key), "hit"

    def read(self, kind: str, key: str) -> bytes:
        path = result_path(kind, key)
        body = self.store.get(path)
        if body is None:
            raise ExportError(f"{path} is not stored; run warm first")
        return body


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = export_demo(
            load_content("demo_cases"),
            Path(args.out),
            store=deps.get_store(),
            reader=deps.get_reader(),
            services=service_table(),
            answers_dir=content_dir() / ANSWERS_FOLDER,
        )
    except (ExportError, ProblemError) as exc:
        reason = f"{exc.code} {exc.detail}" if isinstance(exc, ProblemError) else exc
        print(f"export-demo: wrote nothing: {reason}", file=sys.stderr)
        return FAILED_EXIT_CODE
    print(
        f"export-demo: wrote {len(manifest.cases)} cases to {args.out}", file=sys.stderr
    )
    return 0


def export_demo(
    cases: Sequence[DemoCase],
    out: Path,
    *,
    store: ObjectStore,
    reader: SeriesReader,
    services: Mapping[str, Service],
    answers_dir: Path,
) -> DemoManifest:
    """Write the bundle into out and return its manifest. The services find each
    stored key, and the reader is never read. Raises ExportError, and ProblemError
    for a spec that the catalog refuses; either way it writes nothing."""
    catalog_body = store.get(CATALOG_PATH)
    if catalog_body is None:
        raise ExportError(f"{CATALOG_PATH} is not stored; run build-catalog first")
    catalog = Catalog.model_validate_json(catalog_body)
    results = StoredResults(store)

    def stored(spec: RequestSpec) -> tuple[bytes, str]:
        body, key, _, _ = services[spec.kind](
            spec, reader=reader, results=results, catalog=catalog
        )
        return body, key

    files = {CATALOG_FILE: catalog_body}
    entries = [
        _export_case(case, catalog, stored, results, answers_dir, files)
        for case in cases
    ]
    manifest = DemoManifest(catalog=CATALOG_FILE, cases=entries)
    files[MANIFEST_FILE] = manifest.to_json_bytes()
    _write(files, out)
    return manifest


def _export_case(
    case: DemoCase,
    catalog: Catalog,
    stored: Stored,
    results: StoredResults,
    answers_dir: Path,
    files: dict[str, bytes],
) -> ManifestCase:
    """Add the files of one case to files and return its manifest entry."""
    trend_body, trend_key = stored(case.specs.trend)
    parse = {
        lang: _parse_file(case, lang, catalog, results.store, trend_key, files)
        for lang in LANGS
    }
    kinds = {TREND_KIND: _entry(case, case.specs.trend, trend_key, trend_body, files)}
    referenced: dict[str, dict[str, str]] = {}
    opened = _opened_spec(case, TrendResult.model_validate_json(trend_body))
    if opened is not None:
        body, key = stored(opened)
        kinds[opened.kind] = _entry(case, opened, key, body, files)
        trends = (
            node_trends(body, results.read)
            if opened.kind == CASEBOARD_KIND
            else hit_trends(case.id, body, results.store)
        )
        referenced = _referenced(case, trends, files)
    return ManifestCase(
        case_id=case.id,
        parse=parse,
        kinds=kinds,
        referenced=referenced,
        answers=_answers(case, answers_dir, files),
    )


def _parse_file(
    case: DemoCase,
    lang: Lang,
    catalog: Catalog,
    store: ObjectStore,
    trend_key: str,
    files: dict[str, bytes],
) -> str:
    """The parse answer with the LLM off (a stored model proposal, else the rules),
    checked against the stored trend of the case."""
    text = getattr(case.question, lang)
    cached = parse_cache.get_proposal(
        store, parse_cache.parse_key(text, lang, catalog.version)
    )
    proposal = cached if cached is not None else parse_rules(text, lang, catalog)
    if not proposal.variables:
        raise ExportError(f"{case.id}: the {lang} parse proposes no variable")
    spec = _draft_spec(proposal, case)
    key = result_key(canonicalize(validate_request(spec, catalog), catalog))
    if key != trend_key:
        # The parse cards of the demo would show another analysis than its trend.
        raise ExportError(
            f"{case.id}: the {lang} parse leads to the trend {key}, and the stored"
            f" trend of the case is {trend_key}"
        )
    return _add(files, f"{case.id}/parse.{lang}.json", proposal.to_json_bytes())


def _draft_spec(proposal: ParseProposal, case: DemoCase) -> RequestSpec:
    """The trend spec of the first card on the case area and window, as toDraft of
    web/src/features/rail/draft.ts fills the draft. str of a float can differ from
    String in JavaScript (1.0 against 1); both give one canonical threshold."""
    first = proposal.variables[0]
    parsed = proposal.spec.metric
    metric = SpecMetric(id=first.metric_id)
    if parsed is not None and (parsed.var, parsed.id) == (first.var, first.metric_id):
        metric = SpecMetric(
            id=parsed.id,
            threshold=None if parsed.value is None else str(parsed.value),
            op=parsed.op,
            months=parsed.months,
            season_start=parsed.season_start,
        )
    return RequestSpec(
        v=SPEC_VERSION,
        kind=TREND_KIND,
        var=first.var,
        metric=metric,
        area=case.area,
        window=case.window,
    )


def _opened_spec(case: DemoCase, trend: TrendResult) -> RequestSpec | None:
    """The spec of the panel that the verdict opens: the board for a significant
    verdict, the scan for another verdict, and none with no verdict."""
    if trend.verdict is None:
        return None
    kind = CASEBOARD_KIND if trend.verdict in BOARD_VERDICTS else SCAN_KIND
    spec = getattr(case.specs, kind)
    if spec is None:
        raise ExportError(
            f"{case.id}: the verdict {trend.verdict} opens the {kind}, and the case"
            f" has no {kind} spec"
        )
    return spec


def _referenced(
    case: DemoCase, trends: Mapping[str, bytes], files: dict[str, bytes]
) -> dict[str, dict[str, str]]:
    """referenced of a case: the file of each trend that its board or scan names."""
    paths = {
        key: _add(files, f"{case.id}/trend.{key}.json", body)
        for key, body in trends.items()
    }
    return {TREND_KIND: paths} if paths else {}


def _answers(
    case: DemoCase, answers_dir: Path, files: dict[str, bytes]
) -> ManifestAnswers:
    """The stored guide answers of each language, null where none exist."""
    found = {
        lang: _add(files, f"{case.id}/answers.{lang}.json", source.read_bytes())
        for lang in LANGS
        if (source := answers_dir / f"{case.id}.{lang}.json").is_file()
    }
    return ManifestAnswers(ko=found.get("ko"), en=found.get("en"))


def _entry(
    case: DemoCase, spec: RequestSpec, key: str, body: bytes, files: dict[str, bytes]
) -> ManifestFile:
    """The s is the spec as the browser codec encodes it (content/golden)."""
    path = _add(files, f"{case.id}/{spec.kind}.json", body)
    return ManifestFile(file=path, key=key, s=encode_request_spec(spec))


def _add(files: dict[str, bytes], path: str, body: bytes) -> str:
    files[path] = body
    return path


def _write(files: Mapping[str, bytes], out: Path) -> None:
    for path, body in files.items():
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="export-demo", description=__doc__)
    parser.add_argument("--out", default=DEFAULT_OUT, help="the output folder")
    return parser
