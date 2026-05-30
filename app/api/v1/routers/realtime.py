"""Websocket routes for live application updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.realtime import WebSocketHub


router = APIRouter(prefix="/ws", tags=["Realtime"])


def _get_websocket_hub(websocket: WebSocket) -> WebSocketHub | None:
    return getattr(websocket.app.state, "websocket_hub", None)


@router.websocket("/inventory")
async def inventory_updates(websocket: WebSocket) -> None:
    hub = _get_websocket_hub(websocket)
    if hub is None:
        await websocket.close(code=1011)
        return

    await hub.connect(websocket)
    try:
        await websocket.send_json({"type": "connected", "channel": "inventory"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        await hub.disconnect(websocket)