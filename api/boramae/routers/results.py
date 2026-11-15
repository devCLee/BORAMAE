"""GET /r/{kind}/{key}.json: a stored result by its key, with no validation step.

The service answers this path itself (DEC-003). Only a known kind and a key of the
contract shape reach the store, so no request names any other store path.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from boramae.constants import KEY_HEX_LEN, RESULT_KINDS
from boramae.deps import get_store
from boramae.errors import ProblemError
from boramae.ports import ObjectStore
from boramae.store.results import result_path

router = APIRouter()

JSON_MEDIA_TYPE = "application/json"
# A result file never changes (DATA_MODEL.md "Lifetimes": immutable, 1 year).
RESULT_CACHE_CONTROL = "public, max-age=31536000, immutable"
NOT_FOUND_STATUS = 404
# ponytail: no document names the problem code of a missing result file.
NOT_FOUND_CODE = "not_found"
_KEY_SHAPE = re.compile(rf"[0-9a-f]{{{KEY_HEX_LEN}}}")


@router.get("/r/{kind}/{key}.json")
def get_result_file(
    kind: str,
    key: str,
    request: Request,
    store: Annotated[ObjectStore, Depends(get_store)],
) -> Response:
    is_known = kind in RESULT_KINDS and _KEY_SHAPE.fullmatch(key) is not None
    body = store.get(result_path(kind, key)) if is_known else None
    if body is None:
        raise ProblemError(NOT_FOUND_STATUS, NOT_FOUND_CODE)
    request.state.kind = kind
    request.state.result_key = key
    request.state.cache = "hit"
    return Response(
        body,
        media_type=JSON_MEDIA_TYPE,
        headers={"Cache-Control": RESULT_CACHE_CONTROL},
    )
