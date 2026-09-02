import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Awaitable, Set
import websockets
from websockets.client import WebSocketClientProtocol

from app.core.config import get_settings
from app.services.delta_rest import DeltaRestClient
from app.models.schemas import ConnectionState, MarketTick, Candle, PriceSource
from app.utils.timestamp import normalize_timestamp, format_timestamp_log

logger = logging.getLogger(__name__)


class DeltaWebSocketClient:
    def __init__(self, on_tick: Callable[[MarketTick], Awaitable[None]], on_candle: Callable[[Candle], Awaitable[None]]):
        self.settings = get_settings()
        self.ws_url = self.settings.delta_ws_url
        self.on_tick = on_tick
        self.on_candle = on_candle
        self.ws: Optional[WebSocketClientProtocol] = None
        self.rest_client: Optional[DeltaRestClient] = None
        self.running = False
        self.subscribed_symbols: Set[str] = set()
        self.subscribed_product_ids: Set[int] = set()
        self.connection_state = ConnectionState.DISCONNECTED
        self._reconnect_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_message_time = 0
        self._stale_threshold = 30  # seconds

    async def start(self, rest_client: DeltaRestClient, symbols: List[str]):
        self.rest_client = rest_client
        self.running = True
        await self._subscribe_symbols(symbols)
        asyncio.create_task(self._run())

    async def stop(self):
        self.running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self.ws:
            await self.ws.close()
        self.connection_state = ConnectionState.DISCONNECTED

    async def subscribe(self, symbols: List[str]):
        await self._subscribe_symbols(symbols)

    async def unsubscribe(self, symbols: List[str]):
        exchange_symbols = [self.settings.symbol_mapping[s] for s in symbols if s in self.settings.symbol_mapping]
        if exchange_symbols:
            # Unsubscribe from all channel types
            unsubscribe_msg = {
                "type": "unsubscribe",
                "payload": {
                    "channels": [
                        {"name": "ticker", "symbols": exchange_symbols},
                        {"name": "candlestick_1m", "symbols": exchange_symbols},
                        {"name": "candlestick_5m", "symbols": exchange_symbols},
                        {"name": "candlestick_15m", "symbols": exchange_symbols},
                        {"name": "candlestick_1h", "symbols": exchange_symbols},
                        {"name": "candlestick_4h", "symbols": exchange_symbols},
                        {"name": "mark_price", "symbols": [f"MARK:{s}" for s in exchange_symbols]},
                    ]
                }
            }
            if self.ws and self.ws.open:
                await self.ws.send(json.dumps(unsubscribe_msg))
            self.subscribed_symbols.difference_update(symbols)
            for s in symbols:
                pid = self.rest_client.get_product_id(s) if self.rest_client else None
                if pid:
                    self.subscribed_product_ids.discard(pid)

    async def _subscribe_symbols(self, symbols: List[str]):
        if not self.rest_client:
            logger.error("REST client not initialized")
            return

        new_symbols = [s for s in symbols if s not in self.subscribed_symbols]
        if not new_symbols:
            return

        product_ids = []
        for symbol in new_symbols:
            product_id = self.rest_client.get_product_id(symbol)
            if product_id:
                product_ids.append(product_id)
                self.subscribed_symbols.add(symbol)
                self.subscribed_product_ids.add(product_id)
            else:
                logger.warning(f"Cannot subscribe to {symbol}: no product ID found")

        if not product_ids:
            return

        # Use Delta India public WebSocket channel formats
        exchange_symbols = [self.settings.symbol_mapping[s] for s in new_symbols if s in self.settings.symbol_mapping]
        
        # Build subscription for all channel types
        channels = []
        
        # Ticker channel (includes last traded price, mark price, 24h stats)
        channels.append({"name": "ticker", "symbols": exchange_symbols})
        
        # Candlestick channels for all timeframes
        for tf in self.settings.supported_timeframes:
            channels.append({"name": f"candlestick_{tf.replace('H', 'h')}", "symbols": exchange_symbols})
        
        # Mark price channel (requires MARK: prefix)
        mark_symbols = [f"MARK:{s}" for s in exchange_symbols]
        channels.append({"name": "mark_price", "symbols": mark_symbols})
        
        subscribe_msg = {
            "type": "subscribe",
            "payload": {"channels": channels}
        }

        if self.ws and self.ws.open:
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to channels for {new_symbols}: ticker, candlesticks ({', '.join(self.settings.supported_timeframes)}), mark_price")
        else:
            logger.info(f"Queued subscription for {new_symbols}")

    async def _run(self):
        backoff = 1
        max_backoff = 60

        while self.running:
            try:
                await self._connect()
                backoff = 1
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.connection_state = ConnectionState.RECONNECTING
                await asyncio.sleep(min(backoff, max_backoff))
                backoff = min(backoff * 2, max_backoff)

    async def _connect(self):
        self.connection_state = ConnectionState.CONNECTING
        logger.info(f"Connecting to Delta WS: {self.ws_url}")

        async with websockets.connect(self.ws_url, ping_interval=30, ping_timeout=20, close_timeout=10) as ws:
            self.ws = ws
            self.connection_state = ConnectionState.CONNECTED
            self._last_message_time = time.time()
            logger.info("Delta WS connected")

            # Send initial subscriptions
            if self.subscribed_symbols:
                exchange_symbols = [self.settings.symbol_mapping[s] for s in self.subscribed_symbols if s in self.settings.symbol_mapping]
                
                channels = []
                channels.append({"name": "ticker", "symbols": exchange_symbols})
                for tf in self.settings.supported_timeframes:
                    channels.append({"name": f"candlestick_{tf.replace('H', 'h')}", "symbols": exchange_symbols})
                mark_symbols = [f"MARK:{s}" for s in exchange_symbols]
                channels.append({"name": "mark_price", "symbols": mark_symbols})
                
                subscribe_msg = {
                    "type": "subscribe",
                    "payload": {"channels": channels}
                }
                await ws.send(json.dumps(subscribe_msg))

            # Start heartbeat monitor
            self._heartbeat_task = asyncio.create_task(self._monitor_heartbeat())

            async for message in ws:
                if not self.running:
                    break
                self._last_message_time = time.time()
                await self._handle_message(message)

    async def _monitor_heartbeat(self):
        while self.running:
            await asyncio.sleep(5)
            if time.time() - self._last_message_time > self._stale_threshold:
                if self.connection_state == ConnectionState.CONNECTED:
                    logger.warning("Delta feed appears stale")
                    self.connection_state = ConnectionState.STALE

    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            
            # Log ALL messages for debugging
            logger.info(f"WS RECV: type={msg_type}, keys={list(data.keys()) if isinstance(data, dict) else 'N/A'}")
            
            # Handle subscription confirmation
            if msg_type == "subscriptions":
                logger.info(f"Subscription confirmed: {data}")
                return
            
            # Handle different channel types - Delta public WS uses 'type' field for channel
            if msg_type == "ticker":
                await self._handle_ticker(data)
            elif msg_type and msg_type.startswith("candlestick_"):
                await self._handle_candlestick(data)
            elif msg_type == "mark_price":
                await self._handle_mark_price(data)
            else:
                logger.info(f"Unhandled message type: {msg_type}")

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse WS message: {message[:100]}")
        except Exception as e:
            logger.error(f"Error handling WS message: {e}")

    async def _handle_ticker(self, data: Dict):
        """Handle Delta India ticker channel format."""
        # Ticker message format: {"type": "ticker", "d": {...}, "sp": ..., "sy": "BTCUSD", "ts": ..., "type": "ticker"}
        # Data 'd' contains: product_id, symbol, mark_price, spot_price, last_traded_price, 
        # volume_24h, change_24h, high_24h, low_24h, timestamp
        # Note: 'd' may be a list or dict depending on the message
        try:
            logger.info(f"Ticker handler called with keys: {list(data.keys())}")
            tick_data = data.get("d", {})
            logger.debug(f"Ticker tick_data type: {type(tick_data)}, value: {tick_data}")
            # Handle case where 'd' is a list (take first element)
            if isinstance(tick_data, list):
                if len(tick_data) == 0:
                    logger.debug("Ticker: 'd' is empty list")
                    return
                tick_data = tick_data[0]
            elif not isinstance(tick_data, dict):
                logger.debug(f"Ticker: 'd' is not dict or list: {type(tick_data)}")
                tick_data = {}
            
            product_id = tick_data.get("product_id")
            symbol = data.get("sy") or tick_data.get("symbol")  # e.g., "BTCUSD"
            server_recv_ms = int(time.time() * 1000)

            if product_id is None:
                logger.debug(f"Ticker: product_id is None, tick_data={tick_data}")
                return

            # Prefer last traded price for trading, fall back to mark price
            price = tick_data.get("last_traded_price") or tick_data.get("mark_price") or tick_data.get("spot_price")
            timestamp = data.get("ts") or tick_data.get("timestamp")
            
            if price is None:
                logger.debug(f"Ticker: price is None for {symbol}, tick_data={tick_data}")
                return

            # Map product_id back to frontend symbol
            frontend_symbol = None
            if self.rest_client:
                frontend_symbol = self.rest_client.get_frontend_symbol_by_product_id(product_id)
            
            if not frontend_symbol and symbol:
                for frontend_sym, delta_sym in self.settings.symbol_mapping.items():
                    if delta_sym == symbol:
                        frontend_symbol = frontend_sym
                        break

            if not frontend_symbol:
                logger.debug(f"No frontend symbol mapping for product_id: {product_id}, symbol: {symbol}")
                return

            # Normalize timestamp with validation
            try:
                normalized = normalize_timestamp(timestamp, "delta_ws_ticker")
                
                # Log detailed timestamp info
                log_msg = format_timestamp_log(normalized, "delta_ws_ticker", float(price), symbol)
                logger.info(log_msg)
                
                if not normalized.is_reasonable:
                    logger.warning(
                        f"[{frontend_symbol}] Ticker timestamp may be historical/replay data: "
                        f"age={normalized.age_seconds:.1f}s, future={normalized.is_future}, "
                        f"warnings={normalized.warnings}"
                    )
                
                ts_ms = normalized.timestamp_ms
                
            except ValueError as e:
                logger.error(f"Failed to normalize timestamp for {symbol}: {e}")
                return
            
            tick = MarketTick(
                symbol=frontend_symbol,
                exchange_symbol=symbol or str(product_id),
                product_id=product_id,
                price=float(price),
                timestamp=ts_ms,
                volume=tick_data.get("volume_24h"),
                price_source=PriceSource.LAST_TRADED,
            )
            logger.info(f"Emitting TICKER tick for {frontend_symbol}: price={price}, ts={ts_ms}ms (UTC: {datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).isoformat()})")
            await self.on_tick(tick)

        except Exception as e:
            logger.error(f"Error handling ticker: {e}", exc_info=True)

    async def _handle_candlestick(self, data: Dict):
        """Handle Delta India candlestick channel format."""
        # Candlestick format: {"type": "candlestick_1m", "c": close, "cst": ..., "h": high, "l": low, "o": open, "res": "1m", "sy": "BTCUSD", "ts": timestamp, "type": "candlestick_1m", "v": volume}
        try:
            product_id = None  # Not directly provided, need to map from symbol
            symbol = data.get("sy")  # e.g., "BTCUSD"
            channel = data.get("type")  # e.g., "candlestick_1m"
            
            if not symbol or not channel:
                return

            # Map symbol to frontend symbol
            frontend_symbol = None
            for frontend_sym, delta_sym in self.settings.symbol_mapping.items():
                if delta_sym == symbol:
                    frontend_symbol = frontend_sym
                    break

            if not frontend_symbol:
                logger.debug(f"No frontend symbol mapping for symbol: {symbol}")
                return

            # Extract timeframe from channel
            timeframe_map = {
                "candlestick_1m": "1m",
                "candlestick_5m": "5m",
                "candlestick_15m": "15m",
                "candlestick_1h": "1h",
                "candlestick_4h": "4h",
            }
            timeframe = timeframe_map.get(data.get("type"), "15m")

            # Normalize timestamp
            timestamp = data.get("ts")
            try:
                normalized = normalize_timestamp(timestamp, f"delta_ws_candlestick_{timeframe}")
                ts_ms = normalized.timestamp_ms
            except ValueError as e:
                logger.error(f"Failed to normalize candlestick timestamp for {symbol}: {e}")
                return

            candle = Candle(
                symbol=frontend_symbol,
                timeframe=timeframe,
                timestamp=normalized.timestamp_ms,
                open=float(data.get("o", 0)),
                high=float(data.get("h", 0)),
                low=float(data.get("l", 0)),
                close=float(data.get("c", 0)),
                volume=float(data.get("v", 0)),
                is_complete=data.get("cst") == 1,  # cst=1 means candle closed
            )
            logger.info(f"Emitting CANDLE for {frontend_symbol} {timeframe}: O={candle.open} H={candle.high} L={candle.low} C={candle.close} V={candle.volume} complete={candle.is_complete}")
            await self.on_candle(candle)

        except Exception as e:
            logger.error(f"Error handling candlestick: {e}")

    async def _handle_mark_price(self, data: Dict):
        """Handle Delta India mark_price channel format (MARK: prefixed)."""
        # Mark price format: {"type": "mark_price", "p": price, "sy": "MARK:BTCUSD", "ts": timestamp, "type": "mark_price"}
        try:
            price_data = data
            product_id = None  # Not directly in mark_price
            symbol = data.get("sy")  # e.g., "MARK:BTCUSD"
            server_recv_ms = int(time.time() * 1000)

            if price_data.get("p") is None:
                return

            # Extract base symbol from MARK: prefix
            base_symbol = symbol.replace("MARK:", "") if symbol and symbol.startswith("MARK:") else symbol

            # Map base_symbol to product_id via REST client
            product_id = None
            if self.rest_client:
                for frontend_sym, delta_sym in self.settings.symbol_mapping.items():
                    if delta_sym == base_symbol:
                        product_id = self.rest_client.get_product_id(frontend_sym)
                        break

            if not product_id:
                logger.debug(f"No product_id mapping for base_symbol: {base_symbol}")
                return

            # Map product_id back to frontend symbol
            frontend_symbol = None
            if self.rest_client:
                frontend_symbol = self.rest_client.get_frontend_symbol_by_product_id(product_id)
            
            if not frontend_symbol and base_symbol:
                for frontend_sym, delta_sym in self.settings.symbol_mapping.items():
                    if delta_sym == base_symbol:
                        frontend_symbol = frontend_sym
                        break

            if not frontend_symbol:
                logger.debug(f"No frontend symbol mapping for product_id: {product_id}, symbol: {symbol}")
                return

            # Normalize timestamp with validation
            timestamp = price_data.get("ts")
            try:
                normalized = normalize_timestamp(timestamp, "delta_ws_mark_price")
                
                # Log detailed timestamp info
                log_msg = format_timestamp_log(normalized, "delta_ws_mark_price", float(price_data.get("p", 0)), base_symbol)
                logger.info(log_msg)
                
                if not normalized.is_reasonable:
                    logger.warning(
                        f"[{frontend_symbol}] Mark price timestamp may be historical/replay data: "
                        f"age={normalized.age_seconds:.1f}s, future={normalized.is_future}, "
                        f"warnings={normalized.warnings}"
                    )
                
                ts_ms = normalized.timestamp_ms
                
            except ValueError as e:
                logger.error(f"Failed to normalize timestamp for {base_symbol}: {e}")
                return
            
            tick = MarketTick(
                symbol=frontend_symbol,
                exchange_symbol=base_symbol or str(product_id),
                product_id=product_id,
                price=float(price_data.get("p", 0)),
                timestamp=ts_ms,
                volume=None,
                price_source=PriceSource.MARK_PRICE,
            )
            logger.info(f"Emitting MARK_PRICE tick for {frontend_symbol}: price={price_data.get('p')}, ts={ts_ms}ms (UTC: {datetime.fromtimestamp(ts_ms/1000, tz=timezone.utc).isoformat()})")
            await self.on_tick(tick)

        except Exception as e:
            logger.error(f"Error handling mark_price: {e}")