import asyncio
import json
import logging
from typing import Dict, List, Set, Optional
from fastapi import WebSocket

from app.core.config import get_settings
from app.services.delta_rest import DeltaRestClient
from app.models.schemas import ConnectionState, MarketTick, Candle, WSMessage, WSMessageType
from app.utils.timestamp import normalize_timestamp, format_timestamp_log

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, Set[str]] = {}
        self.symbol_subscribers: Dict[str, Set[WebSocket]] = {}
        self.market_data_service = None  # Will be set externally

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()
        logger.info(f"FRONTEND_WS_CLIENT_CONNECTED client_id={id(websocket)} Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        subscribed = self.active_connections.pop(websocket, set())
        for symbol in subscribed:
            if symbol in self.symbol_subscribers:
                self.symbol_subscribers[symbol].discard(websocket)
                logger.info(f"SUBSCRIBER_UNREGISTERED client_id={id(websocket)} symbol={symbol} remaining_subscribers={len(self.symbol_subscribers.get(symbol, set()))}")
        logger.info(f"FRONTEND_WS_CLIENT_DISCONNECTED client_id={id(websocket)} Total connections: {len(self.active_connections)}")

    async def _handle_connection_close(self, websocket: WebSocket, close_code: int = None):
        """Handle WebSocket connection close"""
        logger.info(f"WebSocket connection closed, code: {close_code}")
        self.disconnect(websocket)

    async def subscribe(self, websocket: WebSocket, symbols: List[str]):
        logger.info(f"SUBSCRIBE_REQUEST client_id={id(websocket)} symbols={symbols}")
        for symbol in symbols:
            self.active_connections[websocket].add(symbol)
            if symbol not in self.symbol_subscribers:
                self.symbol_subscribers[symbol] = set()
            self.symbol_subscribers[symbol].add(websocket)
            logger.info(f"SUBSCRIBER_REGISTERED client_id={id(websocket)} symbol={symbol} total_subscribers={len(self.symbol_subscribers[symbol])}")

        # Subscribe in market data service
        if self.market_data_service:
            await self.market_data_service.subscribe(symbols)

        # Send snapshot for each symbol
        for symbol in symbols:
            snapshot = self.market_data_service.get_snapshot(symbol) if self.market_data_service else None
            if snapshot:
                await self._send_to_ws(websocket, WSMessage(
                    type=WSMessageType.MARKET_SNAPSHOT,
                    payload=snapshot.model_dump()
                ))
                logger.info(f"SNAPSHOT_SENT client_id={id(websocket)} symbol={symbol}")
            else:
                logger.warning(f"No snapshot available for symbol: {symbol}")

    async def unsubscribe(self, websocket: WebSocket, symbols: List[str]):
        for symbol in symbols:
            self.active_connections[websocket].discard(symbol)
            if symbol in self.symbol_subscribers:
                self.symbol_subscribers[symbol].discard(websocket)

        if self.market_data_service:
            await self.market_data_service.unsubscribe(symbols)

    async def handle_message(self, websocket: WebSocket, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            logger.info(f"Received message type: {msg_type} from client client_id={id(websocket)}")
            logger.debug(f"Raw message: {message[:200]}")

            if msg_type == "subscribe":
                req = SubscribeRequest(**data)
                logger.info(f"Subscribe request for symbols: {req.symbols} from client_id={id(websocket)}")
                await self.subscribe(websocket, req.symbols)
            elif msg_type == "unsubscribe":
                req = UnsubscribeRequest(**data)
                await self.unsubscribe(websocket, req.symbols)
            else:
                logger.warning(f"Unknown message type: {msg_type} from client_id={id(websocket)}")

        except Exception as e:
            logger.error(f"Error handling client message: {e}", exc_info=True)
            await self._send_to_ws(websocket, WSMessage(
                type=WSMessageType.ERROR,
                payload={"message": str(e)}
            ))

    async def broadcast_tick(self, tick: MarketTick):
        logger.info(f"Broadcasting tick for {tick.symbol}: {tick.price}")
        if tick.symbol in self.symbol_subscribers:
            message = WSMessage(
                type=WSMessageType.MARKET_TICK,
                payload=tick.model_dump()
            )
            await self._broadcast_to_symbol(tick.symbol, message)
        else:
            logger.warning(f"No subscribers for symbol {tick.symbol}")

    async def broadcast_candle(self, candle: Candle):
        logger.info(f"Broadcasting candle for {candle.symbol}")
        if candle.symbol in self.symbol_subscribers:
            message = WSMessage(
                type=WSMessageType.CANDLE_UPDATE,
                payload=candle.model_dump()
            )
            await self._broadcast_to_symbol(candle.symbol, message)
        else:
            logger.warning(f"No subscribers for symbol {candle.symbol}")

    async def broadcast_connection_status(self, state: ConnectionState):
        logger.info(f"Broadcasting connection status: {state.value}")
        message = WSMessage(
            type=WSMessageType.CONNECTION_STATUS,
            payload={"state": state.value}
        )
        await self._broadcast_all(message)

    async def _broadcast_to_symbol(self, symbol: str, message: WSMessage):
        if symbol in self.symbol_subscribers:
            dead_connections = set()
            for ws in self.symbol_subscribers[symbol]:
                try:
                    await ws.send_text(message.model_dump_json())
                except Exception as e:
                    logger.error(f"Error broadcasting to symbol {symbol}: {e}")
                    dead_connections.add(ws)
            for ws in dead_connections:
                self.disconnect(ws)

    async def _broadcast_all(self, message: WSMessage):
        logger.info(f"Broadcasting to all connections: {message.type}")
        dead_connections = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(message.model_dump_json())
            except Exception as e:
                logger.error(f"Error broadcasting to all: {e}")
                dead_connections.add(ws)
        for ws in dead_connections:
            self.disconnect(ws)

    async def _send_to_ws(self, websocket: WebSocket, message: WSMessage):
        try:
            await websocket.send_text(message.model_dump_json())
        except Exception as e:
            logger.error(f"Error sending to websocket: {e}")