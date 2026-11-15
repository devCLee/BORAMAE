from fastapi import APIRouter

from boramae.errors import ProblemError

router = APIRouter()


# Stub until W4-CASEBOARD-API replaces this file.
@router.get("/api/v1/caseboard")
def get_caseboard() -> None:
    raise ProblemError(501, "not_built")
