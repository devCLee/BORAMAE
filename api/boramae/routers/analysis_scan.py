from fastapi import APIRouter

from boramae.errors import ProblemError

router = APIRouter()


# Stub until W4-SCAN-API replaces this file.
@router.get("/api/v1/scan")
def get_scan() -> None:
    raise ProblemError(501, "not_built")
