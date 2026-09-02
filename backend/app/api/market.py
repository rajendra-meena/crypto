from fastapi import APIRouter, Query, Depends, HTTPException
from typing import List, Optional
from app.services.market_data import MarketDataService
from app.models.schemas import MarketSnapshot, Candle

router = APIRouter(prefix="/api/market", tags=["market"])

market_data_service: MarketDataService = None


def get_market_data_service() -> MarketDataService:
    return market_data_service


@router.get("/symbols", response_model=List[str])
async def get_available_symbols(service: MarketDataService = Depends(get_market_data_service)):
    return list(service.symbol_states.keys())


@router.get("/snapshot/{symbol}", response_model=MarketSnapshot)
async def get_snapshot(symbol: str, service: MarketDataService = Depends(get_market_data_service)):
    snapshot = service.get_snapshot(symbol.upper())
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    return snapshot


@router.get("/candles/{symbol}", response_model=List[Candle])
async def get_candles(
    symbol: str,
    timeframe: str = Query("15m", regex="^(1m|5m|15m|1H|4H)$"),
    limit: int = Query(100, ge=1, le=500),
    service: MarketDataService = Depends(get_market_data_service),
):
    symbol = symbol.upper()
    if symbol not in service.symbol_states:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
    return service.symbol_states[symbol].get_candles(timeframe, limit)