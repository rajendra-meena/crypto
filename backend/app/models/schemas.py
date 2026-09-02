from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class ConnectionState(str, Enum):
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    MOCK = "MOCK"


class PriceSource(str, Enum):
    LAST_TRADED = "last_traded"
    MARK_PRICE = "mark_price"
    INDEX_PRICE = "index_price"
    SPOT_PRICE = "spot_price"


class MarketTick(BaseModel):
    symbol: str
    exchange_symbol: str
    product_id: int
    price: float
    timestamp: int
    volume: Optional[float] = None
    price_source: PriceSource = PriceSource.LAST_TRADED


class Candle(BaseModel):
    symbol: str
    timeframe: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_complete: bool = False


class MarketSnapshot(BaseModel):
    symbol: str
    current_price: float
    mark_price: Optional[float] = None
    index_price: Optional[float] = None
    candles: List[Candle] = []
    connection_state: ConnectionState = ConnectionState.CONNECTING
    last_update: int = 0


class WSMessageType(str, Enum):
    MARKET_TICK = "market_tick"
    CANDLE_UPDATE = "candle_update"
    MARKET_SNAPSHOT = "market_snapshot"
    CONNECTION_STATUS = "connection_status"
    ERROR = "error"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"


class WSMessage(BaseModel):
    type: WSMessageType
    payload: dict
    timestamp: int = Field(default_factory=lambda: int(datetime.utcnow().timestamp() * 1000))


class SubscribeRequest(BaseModel):
    type: Literal["subscribe"] = "subscribe"
    symbols: List[str]


class UnsubscribeRequest(BaseModel):
    type: Literal["unsubscribe"] = "unsubscribe"
    symbols: List[str]


class HealthResponse(BaseModel):
    status: str
    delta_connection_state: ConnectionState
    market_feed: str
    connected_symbols: List[str]
    live_symbols: List[str]
    stale_symbols: List[str]
    no_data_symbols: List[str]
    unavailable_symbols: List[str]
    last_tick_timestamp: int
    uptime_seconds: float


class MarketStatusResponse(BaseModel):
    mode: str
    delta_connection_state: ConnectionState
    subscribed_symbols: List[str]
    symbol_states: dict
    last_tick: dict