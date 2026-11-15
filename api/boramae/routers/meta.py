"""GET /meta/catalog.json: the catalog, the one stored file that changes in place."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from boramae.deps import get_store
from boramae.errors import ProblemError
from boramae.ports import ObjectStore
from boramae.store.results import HEADER_RETRY_AFTER, RETRY_AFTER_S

router = APIRouter()

CATALOG_PATH = "meta/catalog.json"
JSON_MEDIA_TYPE = "application/json"
# System Design "API": 5 min, stale-while-revalidate. ponytail: no document fixes the
# stale window; 5 min is safe because the warm job swaps the catalog last.
CATALOG_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=300"
UNAVAILABLE_STATUS = 503
# ponytail: no document names the problem code of a catalog that is not built yet.
CATALOG_MISSING_CODE = "catalog_unavailable"


@router.get("/meta/catalog.json")
def get_catalog_file(store: Annotated[ObjectStore, Depends(get_store)]) -> Response:
    body = store.get(CATALOG_PATH)
    if body is None:
        raise ProblemError(
            UNAVAILABLE_STATUS,
            CATALOG_MISSING_CODE,
            headers={HEADER_RETRY_AFTER: str(RETRY_AFTER_S)},
        )
    return Response(
        body,
        media_type=JSON_MEDIA_TYPE,
        headers={"Cache-Control": CATALOG_CACHE_CONTROL},
    )
