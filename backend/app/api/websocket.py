from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.ws.manager import ConnectionManager
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/ws", tags=["websocket"])

connection_manager: ConnectionManager = None
market_data_service: MarketDataService = None


def get_connection_manager() -> ConnectionManager:
    return connection_manager


def get_market_data_service() -> MarketDataService:
    return market_data_service


ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]


@router.websocket("/market")
async def websocket_market(
    websocket: WebSocket,
    manager: ConnectionManager = Depends(get_connection_manager),
    service: MarketDataService = Depends(get_market_data_service),
):
    # Validate browser origin before accepting the WebSocket upgrade.
    origin = websocket.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        await websocket.close(code=1008)
        return

    # ConnectionManager owns websocket.accept() so the socket is accepted exactly once.
    await manager.connect(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            await manager.handle_message(websocket, message)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
