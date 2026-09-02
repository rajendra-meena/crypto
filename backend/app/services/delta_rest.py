import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import httpx

from app.core.config import get_settings
from app.models.schemas import ConnectionState

logger = logging.getLogger(__name__)


class DeltaRestClient:
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.delta_base_url
        self.client: Optional[httpx.AsyncClient] = None
        self._product_cache: Dict[str, Dict] = {}
        self._symbol_to_product_id: Dict[str, int] = {}
        self._product_id_to_symbol: Dict[int, str] = {}  # product_id -> exchange symbol (e.g., BTCUSD)
        self._product_id_to_frontend_symbol: Dict[int, str] = {}  # product_id -> frontend symbol (e.g., BTCUSDT)

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        await self.discover_products()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def discover_products(self) -> Dict[str, int]:
        """Discover and map Delta Exchange products for configured symbols."""
        try:
            response = await self.client.get(f"{self.base_url}/v2/products")
            response.raise_for_status()
            products = response.json().get("result", [])

            # Cache all perpetual futures
            for product in products:
                if product.get("contract_type") == "perpetual_futures":
                    symbol = product.get("symbol")
                    product_id = product.get("id")
                    if symbol and product_id:
                        self._product_cache[symbol] = product
                        self._product_id_to_symbol[product_id] = symbol

            # Map frontend symbols to product IDs
            for frontend_symbol, delta_symbol in self.settings.symbol_mapping.items():
                if delta_symbol in self._product_cache:
                    product_id = self._product_cache[delta_symbol]["id"]
                    self._symbol_to_product_id[frontend_symbol] = product_id
                    self._product_id_to_frontend_symbol[product_id] = frontend_symbol
                    logger.info(f"Mapped {frontend_symbol} -> {delta_symbol} (product_id: {product_id})")
                else:
                    logger.warning(f"Product not found for {frontend_symbol} -> {delta_symbol}")

            return self._symbol_to_product_id

        except Exception as e:
            logger.error(f"Failed to discover products: {e}")
            raise

    def get_product_id(self, symbol: str) -> Optional[int]:
        return self._symbol_to_product_id.get(symbol)

    def get_symbol_by_product_id(self, product_id: int) -> Optional[str]:
        return self._product_id_to_symbol.get(product_id)

    def get_frontend_symbol_by_product_id(self, product_id: int) -> Optional[str]:
        return self._product_id_to_frontend_symbol.get(product_id)

    def get_all_product_ids(self) -> List[int]:
        return list(self._symbol_to_product_id.values())

    def get_subscribed_symbols(self) -> List[str]:
        return list(self._symbol_to_product_id.keys())

    def get_product_info(self, symbol: str) -> Optional[Dict]:
        """Get full product info for a frontend symbol."""
        exchange_symbol = self.settings.symbol_mapping.get(symbol)
        if not exchange_symbol:
            return None
        return self._product_cache.get(exchange_symbol)

    def is_product_active(self, symbol: str) -> bool:
        """Check if a product is available and active for trading."""
        info = self.get_product_info(symbol)
        if not info:
            return False
        # Check if product state is live/operational
        state = info.get("state", "").lower()
        trading_status = info.get("trading_status", "").lower()
        return state in ("live", "operational") or trading_status in ("live", "operational")

    def get_unavailable_symbols(self) -> List[str]:
        """Get list of configured symbols that are unavailable."""
        unavailable = []
        for frontend_symbol in self.settings.symbol_mapping.keys():
            if not self.is_product_active(frontend_symbol):
                unavailable.append(frontend_symbol)
        return unavailable

    async def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ) -> List[Dict]:
        """Get historical candles from Delta Exchange."""
        # Use exchange symbol (e.g., BTCUSD) for the API
        exchange_symbol = self.settings.symbol_mapping.get(symbol)
        if not exchange_symbol:
            raise ValueError(f"No exchange symbol mapping for: {symbol}")

        # Convert timeframe to Delta format
        tf_map = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "1H": "1h",
            "4H": "4h",
        }
        delta_tf = tf_map.get(timeframe, "15m")

        params = {
            "symbol": exchange_symbol,
            "resolution": delta_tf,
        }
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        else:
            # Default to last 24 hours if no time range specified
            import time
            end_ts = int(time.time())
            start_ts = end_ts - 86400
            params["start"] = start_ts
            params["end"] = end_ts

        try:
            response = await self.client.get(f"{self.base_url}/v2/history/candles", params=params)
            response.raise_for_status()
            data = response.json().get("result", [])
            logger.debug(f"Fetched {len(data)} candles for {symbol} {timeframe}")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch candles for {symbol}: {e}")
            raise

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get current ticker for a symbol."""
        product_id = self.get_product_id(symbol)
        if not product_id:
            return None

        try:
            response = await self.client.get(f"{self.base_url}/v2/tickers/{product_id}")
            response.raise_for_status()
            return response.json().get("result")
        except Exception as e:
            logger.error(f"Failed to fetch ticker for {symbol}: {e}")
            return None