import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import get_settings
from app.core.database import paper_db
from app.services.market_data import MarketDataService
from app.services.strategy_engine import CryptoStrategyEngine
from app.ws.manager import ConnectionManager
from app.api import health, market, websocket, trading
from app.models.schemas import PriceSource


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
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
logger = structlog.get_logger()

market_data_service: MarketDataService = None
connection_manager: ConnectionManager = None
algo_engine: CryptoStrategyEngine = None
settings = get_settings()
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global market_data_service, connection_manager, algo_engine

    logger.info("Starting backend", version="3.2.0", mode=settings.market_data_mode)
    paper_db.initialize()
    logger.info("Trading database initialized", path=str(paper_db.db_path))

    market_data_service = MarketDataService()
    connection_manager = ConnectionManager()
    connection_manager.market_data_service = market_data_service

    health.market_data_service = market_data_service
    market.market_data_service = market_data_service
    websocket.connection_manager = connection_manager
    websocket.market_data_service = market_data_service

    await market_data_service.start(DEFAULT_SYMBOLS)

    algo_engine = CryptoStrategyEngine(market_data_service)
    trading.market_data_service = market_data_service
    trading.algo_engine = algo_engine

    original_broadcast_tick = connection_manager.broadcast_tick
    original_broadcast_candle = connection_manager.broadcast_candle

    async def on_tick_bridge(tick):
        await original_broadcast_tick(tick)
        if tick.price_source in (PriceSource.LAST_TRADED, PriceSource.SPOT_PRICE):
            await algo_engine.on_tick(tick.symbol, float(tick.price))

    async def on_candle_bridge(candle):
        await original_broadcast_candle(candle)
        if candle.is_complete:
            await algo_engine.on_completed_candle(candle.symbol)

    market_data_service._broadcast_tick_update = on_tick_bridge
    market_data_service._broadcast_candle_update = on_candle_bridge

    async def scanner_loop():
        while market_data_service.running:
            try:
                await algo_engine.scan_all_symbols()
            except Exception as exc:
                logger.error("Algo scanner iteration failed", error=str(exc))
            await asyncio.sleep(2)

    scanner_task = asyncio.create_task(scanner_loop())
    logger.info(
        "Crypto algo engine started",
        strategy=algo_engine.STRATEGY_VERSION,
        symbols=DEFAULT_SYMBOLS,
        scan_interval_seconds=2,
        execution_mode="PAPER_ONLY",
    )

    yield

    logger.info("Shutting down backend")
    scanner_task.cancel()
    try:
        await scanner_task
    except asyncio.CancelledError:
        pass
    await market_data_service.stop()
    logger.info("Backend stopped")


app = FastAPI(
    title="Delta Crypto Algo Backend",
    description="Real-time Delta market data with backend-authoritative 15m/5m/1m paper trading engine",
    version="3.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(market.router)
app.include_router(websocket.router)
app.include_router(trading.router)


@app.get("/")
async def root():
    return {
        "service": "Delta Crypto Algo Backend",
        "version": "3.2.0",
        "mode": settings.market_data_mode,
        "strategy": algo_engine.STRATEGY_VERSION if algo_engine else CryptoStrategyEngine.STRATEGY_VERSION,
        "execution": "PAPER_ONLY",
        "scanner": "ACTIVE" if algo_engine else "STARTING",
        "trading_api": "/api/trading/state",
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
