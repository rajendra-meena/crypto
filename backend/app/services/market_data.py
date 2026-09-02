import asyncio
import logging
import time
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict
from datetime import datetime

from app.core.config import get_settings
from app.services.delta_rest import DeltaRestClient
from app.services.delta_ws import DeltaWebSocketClient
from app.models.schemas import (
    ConnectionState, MarketTick, Candle, MarketSnapshot,
    MarketStatusResponse, HealthResponse, PriceSource
)

logger = logging.getLogger(__name__)

# Timeframe to seconds mapping
TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1H": 3600,
    "4H": 14400,
}


class CandleAggregator:
    """Aggregates trade/spot ticks into candles for multiple timeframes."""

    def __init__(self, symbol: str, timeframes: List[str]):
        self.symbol = symbol
        self.timeframes = timeframes
        self.current_candles: Dict[str, Dict] = {}
        self.completed_candles: Dict[str, List[Candle]] = defaultdict(list)
        self.max_candles_per_tf = 200

    def _get_candle_key(self, timestamp: int, timeframe: str) -> int:
        tf_seconds = TIMEFRAME_SECONDS[timeframe]
        return (timestamp // 1000 // tf_seconds) * tf_seconds * 1000

    def _init_candle(self, timeframe: str, timestamp: int, price: float, volume: float = 0):
        key = self._get_candle_key(timestamp, timeframe)
        self.current_candles[f"{timeframe}:{key}"] = {
            "symbol": self.symbol,
            "timeframe": timeframe,
            "timestamp": key,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": volume,
            "is_complete": False,
        }

    def update_tick(self, tick: MarketTick) -> List[Candle]:
        updated = []
        for tf in self.timeframes:
            key = self._get_candle_key(tick.timestamp, tf)
            candle_key = f"{tf}:{key}"

            if candle_key not in self.current_candles:
                self._init_candle(tf, tick.timestamp, tick.price, tick.volume or 0)
            else:
                candle = self.current_candles[candle_key]
                candle["high"] = max(candle["high"], tick.price)
                candle["low"] = min(candle["low"], tick.price)
                candle["close"] = tick.price
                candle["volume"] += tick.volume or 0

            updated.append(Candle(**self.current_candles[candle_key]))

        return updated

    def finalize_candles(self, current_time: int) -> List[Candle]:
        finalized = []
        for tf in self.timeframes:
            tf_seconds = TIMEFRAME_SECONDS[tf]
            current_key = (current_time // 1000 // tf_seconds) * tf_seconds * 1000

            keys_to_finalize = [
                k for k in self.current_candles.keys()
                if k.startswith(f"{tf}:") and int(k.split(":")[1]) < current_key
            ]

            for key in keys_to_finalize:
                candle_data = self.current_candles.pop(key)
                candle_data["is_complete"] = True
                candle = Candle(**candle_data)
                self.completed_candles[tf].append(candle)
                finalized.append(candle)

                if len(self.completed_candles[tf]) > self.max_candles_per_tf:
                    self.completed_candles[tf] = self.completed_candles[tf][-self.max_candles_per_tf:]

        return finalized

    def get_current_candles(self, timeframe: str) -> List[Candle]:
        result = []
        for tf in self.timeframes:
            if tf == timeframe:
                for k, v in self.current_candles.items():
                    if k.startswith(f"{tf}:"):
                        result.append(Candle(**v))
        return result

    def get_history(self, timeframe: str, limit: int = 100) -> List[Candle]:
        completed = self.completed_candles.get(timeframe, [])
        current = self.get_current_candles(timeframe)
        return (completed + current)[-limit:]


class SymbolState:
    """Maintains state for a single symbol."""

    def __init__(self, symbol: str, timeframes: List[str]):
        self.symbol = symbol
        self.timeframes = timeframes
        self.aggregator = CandleAggregator(symbol, timeframes)
        self.current_price: float = 0
        self.mark_price: float = 0
        self.index_price: float = 0
        self.last_tick_time: int = 0
        self.last_received_time: float = 0
        self.last_tick: Optional[MarketTick] = None
        self.connection_state = ConnectionState.CONNECTING
        self._historical_loaded = False

    def update_tick(self, tick: MarketTick) -> List[Candle]:
        """Update prices and only aggregate execution-relevant price sources.

        Mark/index prices are useful for diagnostics and liquidation/risk context,
        but must never alter OHLC candles used by the strategy.
        """
        updated_candles: List[Candle] = []
        if tick.price_source in (PriceSource.LAST_TRADED, PriceSource.SPOT_PRICE):
            self.current_price = tick.price
            updated_candles = self.aggregator.update_tick(tick)
        elif tick.price_source == PriceSource.MARK_PRICE:
            self.mark_price = tick.price
        elif tick.price_source == PriceSource.INDEX_PRICE:
            self.index_price = tick.price

        self.last_tick_time = tick.timestamp
        self.last_tick = tick
        return updated_candles

    def finalize_candles(self) -> List[Candle]:
        return self.aggregator.finalize_candles(int(time.time() * 1000))

    def get_candles(self, timeframe: str, limit: int = 100) -> List[Candle]:
        return self.aggregator.get_history(timeframe, limit)

    def load_historical_from_rest(self, candles: List[Dict], timeframe: str):
        seen = {int(c.timestamp) for c in self.aggregator.completed_candles.get(timeframe, [])}
        for h in candles:
            ts = h.get("time", 0)
            if ts < 1e12:
                ts = ts * 1000
            ts = int(ts)
            if ts in seen:
                continue
            candle = Candle(
                symbol=self.symbol,
                timeframe=timeframe,
                timestamp=ts,
                open=float(h.get("open", 0)),
                high=float(h.get("high", 0)),
                low=float(h.get("low", 0)),
                close=float(h.get("close", 0)),
                volume=float(h.get("volume", 0)),
                is_complete=True,
            )
            self.aggregator.completed_candles[timeframe].append(candle)
            seen.add(ts)
        self.aggregator.completed_candles[timeframe].sort(key=lambda c: int(c.timestamp))
        self.aggregator.completed_candles[timeframe] = self.aggregator.completed_candles[timeframe][-self.aggregator.max_candles_per_tf:]
        self._historical_loaded = True

    def get_current_candle(self, timeframe: str) -> Optional[Candle]:
        candles = self.aggregator.get_current_candles(timeframe)
        return candles[0] if candles else None

    def load_historical(self, candles: List[Candle]):
        for candle in candles:
            self.aggregator.completed_candles[candle.timeframe].append(candle)
        for timeframe in self.timeframes:
            deduped = {int(c.timestamp): c for c in self.aggregator.completed_candles.get(timeframe, [])}
            self.aggregator.completed_candles[timeframe] = [deduped[key] for key in sorted(deduped.keys())][-self.aggregator.max_candles_per_tf:]
        self._historical_loaded = True


class MarketDataService:
    """Main market data service coordinating REST, WS, and candle aggregation."""

    def __init__(self):
        self.settings = get_settings()
        self.rest_client: Optional[DeltaRestClient] = None
        self.ws_client: Optional[DeltaWebSocketClient] = None
        self.symbol_states: Dict[str, SymbolState] = {}
        self.running = False
        self._start_time = time.time()
        self._candle_finalizer_task: Optional[asyncio.Task] = None
        self._stale_check_task: Optional[asyncio.Task] = None
        self._delta_stale_check_task: Optional[asyncio.Task] = None
        self._delta_connection_state = ConnectionState.DISCONNECTED
        self._delta_last_message_time = 0.0
        self._delta_stale_threshold = 30.0

    async def start(self, symbols: List[str]):
        logger.info(f"Starting market data service for symbols: {symbols}")
        self.running = True
        self.rest_client = DeltaRestClient()
        await self.rest_client.__aenter__()
        discovered = await self.rest_client.discover_products()

        unavailable_symbols = self.rest_client.get_unavailable_symbols()
        if unavailable_symbols:
            logger.warning(f"Products unavailable on Delta: {unavailable_symbols}")

        available_symbols = [s for s in symbols if s in discovered and s not in unavailable_symbols]
        unavailable = [s for s in symbols if s not in discovered or s in unavailable_symbols]
        if unavailable:
            logger.warning(f"Symbols unavailable on Delta: {unavailable}")

        for symbol in available_symbols:
            self.symbol_states[symbol] = SymbolState(symbol, self.settings.supported_timeframes)
            for tf in self.settings.supported_timeframes:
                try:
                    historical = await self.rest_client.get_historical_candles(symbol, tf, limit=100)
                    self.symbol_states[symbol].load_historical_from_rest(historical, tf)
                    logger.info(f"Loaded {len(historical)} historical candles for {symbol} {tf}")
                except Exception as e:
                    logger.error(f"Failed to load historical candles for {symbol} {tf}: {e}")

        self.ws_client = DeltaWebSocketClient(on_tick=self._handle_tick, on_candle=self._handle_candle)
        await self.ws_client.start(self.rest_client, available_symbols)
        self._candle_finalizer_task = asyncio.create_task(self._finalize_candles_loop())
        self._stale_check_task = asyncio.create_task(self._stale_check_loop())
        self._delta_stale_check_task = asyncio.create_task(self._delta_stale_check_loop())
        logger.info("Market data service started")

    async def stop(self):
        logger.info("Stopping market data service")
        self.running = False
        for task in (self._candle_finalizer_task, self._stale_check_task, self._delta_stale_check_task):
            if task:
                task.cancel()
        if self.ws_client:
            await self.ws_client.stop()
        if self.rest_client:
            await self.rest_client.__aexit__(None, None, None)
        logger.info("Market data service stopped")

    def update_delta_connection_state(self, state: ConnectionState):
        self._delta_connection_state = state
        self._delta_last_message_time = time.time()

    def get_delta_connection_state(self) -> ConnectionState:
        return self._delta_connection_state

    async def _delta_stale_check_loop(self):
        while self.running:
            await asyncio.sleep(5)
            if self._delta_connection_state == ConnectionState.CONNECTED:
                elapsed = time.time() - self._delta_last_message_time
                if elapsed > self._delta_stale_threshold:
                    self._delta_connection_state = ConnectionState.STALE
                    logger.warning(f"Delta feed stale: no message for {elapsed:.1f}s")

    async def subscribe(self, symbols: List[str]):
        for symbol in symbols:
            if symbol not in self.symbol_states and self.rest_client:
                product_id = self.rest_client.get_product_id(symbol)
                if product_id:
                    self.symbol_states[symbol] = SymbolState(symbol, self.settings.supported_timeframes)
                    for tf in self.settings.supported_timeframes:
                        try:
                            historical = await self.rest_client.get_historical_candles(symbol, tf, limit=100)
                            self.symbol_states[symbol].load_historical_from_rest(historical, tf)
                        except Exception as e:
                            logger.error(f"Failed to load historical for {symbol} {tf}: {e}")
        if self.ws_client:
            await self.ws_client.subscribe(symbols)

    async def unsubscribe(self, symbols: List[str]):
        if self.ws_client:
            await self.ws_client.unsubscribe(symbols)

    async def _handle_tick(self, tick: MarketTick):
        if tick.symbol not in self.symbol_states:
            logger.warning(f"Tick for unknown symbol: {tick.symbol}")
            return

        state = self.symbol_states[tick.symbol]
        state.connection_state = ConnectionState.CONNECTED
        state.last_received_time = time.time()
        self._delta_connection_state = ConnectionState.CONNECTED
        self._delta_last_message_time = time.time()
        updated_candles = state.update_tick(tick)

        for candle in updated_candles:
            await self._broadcast_candle_update(candle)
        await self._broadcast_tick_update(tick)

    async def _broadcast_tick_update(self, tick: MarketTick):
        pass

    async def _handle_candle(self, candle: Candle):
        if candle.symbol in self.symbol_states:
            self.symbol_states[candle.symbol].aggregator.current_candles[f"{candle.timeframe}:{candle.timestamp}"] = candle.model_dump()
            await self._broadcast_candle_update(candle)

    async def _broadcast_candle_update(self, candle: Candle):
        pass

    async def _finalize_candles_loop(self):
        while self.running:
            await asyncio.sleep(5)
            for state in self.symbol_states.values():
                for candle in state.finalize_candles():
                    await self._broadcast_candle_update(candle)

    async def _stale_check_loop(self):
        while self.running:
            await asyncio.sleep(10)
            now = time.time()
            for state in self.symbol_states.values():
                if state.last_received_time > 0:
                    elapsed = now - state.last_received_time
                    if elapsed > 30 and state.connection_state == ConnectionState.CONNECTED:
                        state.connection_state = ConnectionState.STALE
                        logger.warning(f"Stale feed detected for {state.symbol}")

    def get_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        if symbol not in self.symbol_states:
            return None
        state = self.symbol_states[symbol]
        candles = []
        for tf in self.settings.supported_timeframes:
            candles.extend(state.get_candles(tf, limit=50))
        return MarketSnapshot(
            symbol=symbol,
            current_price=state.current_price,
            mark_price=state.mark_price if state.mark_price > 0 else None,
            index_price=state.index_price if state.index_price > 0 else None,
            candles=candles,
            connection_state=state.connection_state,
            last_update=state.last_tick_time,
        )

    def get_all_snapshots(self) -> Dict[str, MarketSnapshot]:
        return {symbol: self.get_snapshot(symbol) for symbol in self.symbol_states}

    def get_health(self) -> HealthResponse:
        live_symbols = []
        stale_symbols = []
        no_data_symbols = []
        unavailable_symbols = []
        now = time.time()

        for symbol, state in self.symbol_states.items():
            if state.current_price == 0 and state.last_tick_time == 0:
                no_data_symbols.append(symbol)
                continue
            elapsed = now - state.last_received_time if state.last_received_time > 0 else float('inf')
            if elapsed <= 30:
                live_symbols.append(symbol)
            else:
                stale_symbols.append(symbol)

        if self.rest_client:
            unavailable_symbols = self.rest_client.get_unavailable_symbols()

        last_tick = max((state.last_tick_time for state in self.symbol_states.values()), default=0)
        status = "healthy" if live_symbols else "degraded"
        market_feed = "live" if live_symbols else "stale"
        return HealthResponse(
            status=status,
            delta_connection_state=self._delta_connection_state,
            market_feed=market_feed,
            connected_symbols=list(self.symbol_states.keys()),
            live_symbols=live_symbols,
            stale_symbols=stale_symbols,
            no_data_symbols=no_data_symbols,
            unavailable_symbols=unavailable_symbols,
            last_tick_timestamp=last_tick,
            uptime_seconds=int(time.time() - self._start_time),
        )


market_data_service = MarketDataService()
