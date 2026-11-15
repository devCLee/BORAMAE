from fastapi import APIRouter, WebSocket

router = APIRouter()


# Stub until W5-GUIDE-API replaces this file: one error message, then close.
# ponytail: the "type" member is a guess at the discriminator of contracts/agent.py.
@router.websocket("/api/v1/agent")
async def agent_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "error", "code": "not_built"})
    await websocket.close()
