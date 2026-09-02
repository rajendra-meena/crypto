from pydantic_settings import BaseSettings
from typing import List, Dict
from functools import lru_cache


class Settings(BaseSettings):
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_reload: bool = True

    delta_base_url: str = "https://api.india.delta.exchange"
    delta_ws_url: str = "wss://public-socket.india.delta.exchange"

    market_data_mode: str = "REAL"

    # Local persistent database for paper positions, closed trades and executed signals.
    # Override with DATABASE_PATH in backend/.env when required.
    database_path: str = "data/crypto_algo.db"

    log_level: str = "INFO"
    log_format: str = "json"

    # Symbol mapping: frontend symbol -> delta product symbol
    symbol_mapping: Dict[str, str] = {
        "BTCUSDT": "BTCUSD",
        "ETHUSDT": "ETHUSD",
        "SOLUSDT": "SOLUSD",
        "XRPUSDT": "XRPUSD",
        "BNBUSDT": "BNBUSD",
    }

    supported_timeframes: List[str] = ["1m", "5m", "15m", "1H", "4H"]

    # Delta Exchange public WebSocket channels (per official docs)
    delta_channels: Dict[str, str] = {
        "ticker": "ticker",
        "candlestick_1m": "candlestick_1m",
        "candlestick_5m": "candlestick_5m",
        "candlestick_15m": "candlestick_15m",
        "candlestick_1h": "candlestick_1h",
        "candlestick_4h": "candlestick_4h",
        "mark_price": "mark_price",
    }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
