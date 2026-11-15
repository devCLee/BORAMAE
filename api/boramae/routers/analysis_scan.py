"""GET /api/v1/scan?s=: the no-trend fallback of a focus area and window (FR-19).

The router hands the request facts to the request-log middleware on request.state
(docs/BUILD_CONTRACT.md "Request facts and headers") and answers the stored bytes.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from boramae.contracts.results_catalog import Catalog
from boramae.deps import get_catalog, get_reader, get_results
from boramae.ports import SeriesReader
from boramae.services.scan import SCAN_KIND, get_scan
from boramae.spec.validate import decode_s
from boramae.store.results import ResultService

router = APIRouter()

JSON_MEDIA_TYPE = "application/json"


# A missing s decodes as an invalid spec, so it gets the 400 problem body and not the
# 422 of FastAPI.
@router.get("/api/v1/scan")
def get_scan_result(
    request: Request,
    reader: Annotated[SeriesReader, Depends(get_reader)],
    results: Annotated[ResultService, Depends(get_results)],
    catalog: Annotated[Catalog, Depends(get_catalog)],
    s: str = "",
) -> Response:
    body, key, cache, facts = get_scan(
        decode_s(s), reader=reader, results=results, catalog=catalog
    )
    state = request.state
    state.kind = SCAN_KIND
    state.result_key = key
    state.cache = cache
    state.bytes_fetched = facts.bytes_fetched
    state.timings = facts.timings
    state.used_containing_cell = facts.used_containing_cell
    return Response(body, media_type=JSON_MEDIA_TYPE)
