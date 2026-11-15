from fastapi import APIRouter

from boramae.errors import ProblemError

router = APIRouter()


# Stub until W3-TREND-SVC replaces this file.
@router.get("/api/v1/trend")
def get_trend() -> None:
    raise ProblemError(501, "not_built")
