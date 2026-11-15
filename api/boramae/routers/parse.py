"""POST /api/v1/parse: a typed question to a proposal bound to catalog IDs (FR-03).

The text is untrusted: the body and the text are capped before any work, and the text
is never stored or logged. A cache hit answers first. On a miss, the model parser runs
when the seam supplies one; only its output that passes the catalog check is cached.
A timeout, an error, an invalid output or no parser gives the rules proposal, which is
never cached (TDD.md Flow A).

A model parser is a callable parse(text, lang, catalog, session_id) that returns a
mapping in the ParseProposal shape or raises. The router sets its source to model.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from boramae.constants import MAX_PARSE_CHARS
from boramae.contracts.results_catalog import Catalog
from boramae.contracts.spec import ParseProposal, ParseRequest
from boramae.deps import get_catalog, get_model_parser, get_store
from boramae.errors import ProblemError
from boramae.ports import ObjectStore
from boramae.services import parse_cache
from boramae.services.parser_llm import ModelParser
from boramae.services.parser_rules import parse_rules

router = APIRouter()
log = logging.getLogger(__name__)

JSON_MEDIA_TYPE = "application/json"
BAD_REQUEST = 400
# ponytail: no document names the problem codes of a bad parse request.
INVALID_REQUEST = "invalid_request"
TEXT_TOO_LONG = "text_too_long"
# A JSON escape spells one character in up to 12 bytes (a surrogate pair); the rest
# of the body is the language, the session ID and the keys.
MAX_BODY_BYTES = 12 * MAX_PARSE_CHARS + 1024
KIND = "parse"


@router.post("/api/v1/parse")
async def post_parse(
    request: Request,
    store: Annotated[ObjectStore, Depends(get_store)],
    catalog: Annotated[Catalog, Depends(get_catalog)],
    model_parser: Annotated[ModelParser | None, Depends(get_model_parser)],
) -> Response:
    parse_request = _read_request(await _read_capped(request))
    request.state.kind = KIND
    proposal, cache = await run_in_threadpool(
        _answer, parse_request, catalog, store, model_parser
    )
    request.state.cache = cache
    return Response(proposal.to_json_bytes(), media_type=JSON_MEDIA_TYPE)


async def _read_capped(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_BODY_BYTES:
            raise ProblemError(BAD_REQUEST, TEXT_TOO_LONG, "the body is too large")
    return bytes(body)


def _read_request(body: bytes) -> ParseRequest:
    try:
        parse_request = ParseRequest.model_validate_json(body)
    except ValidationError as error:
        # The detail names no field value, because a value can be the text itself.
        detail = "the body is not a parse request"
        raise ProblemError(BAD_REQUEST, INVALID_REQUEST, detail) from error
    if not parse_request.text.strip():
        raise ProblemError(BAD_REQUEST, INVALID_REQUEST, "the text is empty")
    if len(parse_request.text) > MAX_PARSE_CHARS:
        detail = f"the text is over {MAX_PARSE_CHARS} characters"
        raise ProblemError(BAD_REQUEST, TEXT_TOO_LONG, detail)
    return parse_request


def _answer(
    parse_request: ParseRequest,
    catalog: Catalog,
    store: ObjectStore,
    model_parser: ModelParser | None,
) -> tuple[ParseProposal, str]:
    """The proposal and the cache fact: 'hit' when the store held it, else 'miss'."""
    key = parse_cache.parse_key(parse_request.text, parse_request.lang, catalog.version)
    cached = parse_cache.get_proposal(store, key)
    if cached is not None:
        return cached, "hit"
    proposal = model_parser and _ask_model(model_parser, parse_request, catalog)
    if proposal:
        parse_cache.put_proposal(store, key, proposal)
        return proposal, "miss"
    return parse_rules(parse_request.text, parse_request.lang, catalog), "miss"


def _ask_model(
    model_parser: ModelParser, parse_request: ParseRequest, catalog: Catalog
) -> ParseProposal | None:
    """The validated model proposal, or None so that the rules answer."""
    try:
        output = model_parser(
            parse_request.text, parse_request.lang, catalog, parse_request.session_id
        )
        proposal = ParseProposal.model_validate({**output, "source": "model"})
    # Any failure of the seam (a timeout, a client error, a spent budget, an output of
    # another shape) must give the rules answer, so the catch is broad on purpose
    # (TR-F-005). The log names only the error type, never the text.
    except Exception as error:  # noqa: BLE001
        log.warning("parse: the model parser failed (%s)", type(error).__name__)
        return None
    if not _is_in_catalog(proposal, catalog):
        log.warning("parse: the model output names an ID outside the catalog")
        return None
    return proposal


def _is_in_catalog(proposal: ParseProposal, catalog: Catalog) -> bool:
    var_ids = {item.id for item in catalog.variables}
    metric_ids = {item.id for item in catalog.metrics}
    pairs = [(item.var, item.metric_id) for item in proposal.variables]
    if proposal.spec.metric is not None:
        pairs.append((proposal.spec.metric.var, proposal.spec.metric.id))
    nearest = proposal.unavailable and proposal.unavailable.nearest_var
    return nearest in {None, *var_ids} and all(
        var in var_ids and metric_id in metric_ids for var, metric_id in pairs
    )
