import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import get_settings
from app.services.market_data import MarketDataService
from app.ws.manager import ConnectionManager
from app.api import health, market, websocket

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    format="%(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)

logger = structlog.get_logger()

# Global instances
market_data_service: MarketDataService = None
connection_manager: ConnectionManager = None
settings = get_settings()

# Default symbols to track
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global market_data_service, connection_manager

    logger.info("Starting backend", version="2.0.0", mode=settings.market_data_mode)

    # Initialize services
    market_data_service = MarketDataService()
    connection_manager = ConnectionManager()
    connection_manager.market_data_service = market_data_service

    # Wire API modules
    health.market_data_service = market_data_service
    market.market_data_service = market_data_service
    websocket.connection_manager = connection_manager
    websocket.market_data_service = market_data_service

    # Start market data service
    await market_data_service.start(DEFAULT_SYMBOLS)

    # Bridge market data events to WebSocket clients
    original_broadcast = connection_manager.broadcast_tick
    original_broadcast_candle = connection_manager.broadcast_candle
    original_broadcast_status = connection_manager.broadcast_connection_status

    async def on_tick_bridge(tick):
        await original_broadcast(tick)

    async def on_candle_bridge(candle):
        await original_broadcast_candle(candle)

    # Replace the service's internal broadcast with our bridge
    market_data_service._broadcast_candle_update = on_candle_bridge
    market_data_service._broadcast_tick_update = on_tick_bridge

    logger.info("Backend started successfully")

    yield

    # Shutdown
    logger.info("Shutting down backend")
    await market_data_service.stop()
    logger.info("Backend stopped")


app = FastAPI(
    title="Delta Algo Terminal - Market Data Backend",
    description="Real-time Delta Exchange market data via WebSocket",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(market.router)
app.include_router(websocket.router)


@app.get("/")
async def root():
    return {
        "service": "Delta Algo Terminal Backend",
        "version": "2.0.0",
        "mode": settings.market_data_mode,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.backend_reload,
        log_level=settings.log_level.lower(),
    )


@app.get("/")
async def root():
    return {
        "service": "Delta Algo Terminal Backend",
        "version": "2.0.0",
        "mode": settings.market_data_mode,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.backend_reload,
        log_level=settings.log_level.lower(),
    )