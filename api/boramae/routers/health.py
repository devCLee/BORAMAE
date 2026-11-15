from fastapi import APIRouter

router = APIRouter()


# Answers from memory and reads no dependency (TDD.md:404).
@router.get("/health")
def get_health() -> dict[str, str]:
    return {"status": "ok"}
