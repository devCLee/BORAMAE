from fastapi import APIRouter

from boramae.errors import ProblemError

router = APIRouter()


# Stub until W3-PARSER replaces this file.
@router.post("/api/v1/parse")
def post_parse() -> None:
    raise ProblemError(501, "not_built")
