import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import paper_db
from app.services.paper_engine import DEFAULT_TRADING_SETTINGS


router = APIRouter(prefix="/api/paper", tags=["paper-trading"])
market_data_service = None
paper_engine = None


class EngineStateRequest(BaseModel):
    running: bool


class TradingSettingsRequest(BaseModel):
    settings: Dict[str, Any]


def _require_engine():
    if paper_engine is None:
        raise HTTPException(status_code=503, detail="Paper strategy engine is not ready")
    return paper_engine


def _validated_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = dict(DEFAULT_TRADING_SETTINGS)
    current.update(paper_db.get_trading_settings())
    for key, value in payload.items():
        if key in DEFAULT_TRADING_SETTINGS:
            current[key] = value

    current["capital"] = max(100.0, float(current["capital"]))
    current["riskPerTradePct"] = min(3.0, max(0.1, float(current["riskPerTradePct"])))
    current["maxDailyLossPct"] = min(10.0, max(0.5, float(current["maxDailyLossPct"])))
    current["maxConcurrentTrades"] = min(5, max(1, int(current["maxConcurrentTrades"])))
    current["maxSameDirection"] = min(5, max(1, int(current["maxSameDirection"])))
    current["maxLeverage"] = min(10.0, max(1.0, float(current["maxLeverage"])))
    current["minSetupScore"] = min(95, max(50, int(current["minSetupScore"])))
    current["maxTradesPerDay"] = min(30, max(1, int(current["maxTradesPerDay"])))
    current["maxConsecutiveLosses"] = min(10, max(1, int(current["maxConsecutiveLosses"])))
    current["cooldownMinutes"] = min(1440.0, max(0.0, float(current["cooldownMinutes"])))
    current["atrStopMultiplier"] = min(5.0, max(0.5, float(current["atrStopMultiplier"])))
    current["minStopPct"] = min(3.0, max(0.05, float(current["minStopPct"])))
    current["maxStopPct"] = min(10.0, max(current["minStopPct"], float(current["maxStopPct"])))
    current["targetRR"] = min(5.0, max(1.0, float(current["targetRR"])))
    current["breakEvenAtR"] = min(3.0, max(0.5, float(current["breakEvenAtR"])))
    current["trailStartR"] = min(5.0, max(current["breakEvenAtR"], float(current["trailStartR"])))
    current["trailAtrMultiplier"] = min(5.0, max(0.25, float(current["trailAtrMultiplier"])))
    current["maxTradeMinutes"] = min(1440.0, max(5.0, float(current["maxTradeMinutes"])))
    current["minAtrPct"] = min(5.0, max(0.0, float(current["minAtrPct"])))
    current["maxAtrPct"] = min(20.0, max(current["minAtrPct"], float(current["maxAtrPct"])))
    current["minVolumeRatio"] = min(5.0, max(0.0, float(current["minVolumeRatio"])))
    current["btcTrendFilter"] = bool(current["btcTrendFilter"])
    current["feeRatePct"] = min(1.0, max(0.0, float(current["feeRatePct"])))
    current["slippagePct"] = min(1.0, max(0.0, float(current["slippagePct"])))
    return current


@router.get("/state")
async def get_state():
    return _require_engine().build_state()


@router.get("/signals")
async def get_signals():
    engine = _require_engine()
    return {"signals": engine.get_signals(), "version": engine.STRATEGY_VERSION}


@router.get("/analysis")
async def get_analysis():
    engine = _require_engine()
    return {"analysis": engine.get_analysis(), "version": engine.STRATEGY_VERSION}


@router.get("/analysis/{symbol}")
async def get_symbol_analysis(symbol: str):
    engine = _require_engine()
    normalized = symbol.upper()
    item = engine.latest_analysis.get(normalized)
    if item is None:
        item = engine.analyze_symbol(normalized)
        engine.latest_analysis[normalized] = item
    return item


@router.get("/positions")
async def get_positions():
    return {"positions": list(_require_engine().positions_by_symbol.values())}


@router.get("/trades")
async def get_trades(limit: int = 200):
    safe_limit = min(1000, max(1, int(limit)))
    return {"trades": paper_db.list_closed_trades(safe_limit)}


@router.get("/risk")
async def get_risk():
    return _require_engine().get_risk_summary()


@router.put("/engine")
async def set_engine_state(request: EngineStateRequest):
    paper_db.set_engine_running(request.running, int(time.time() * 1000))
    return {
        "engine_running": request.running,
        "mode": "PAPER_ONLY",
        "message": "Paper auto-execution armed" if request.running else "Paper auto-execution stopped",
    }


@router.put("/settings")
async def set_trading_settings(request: TradingSettingsRequest):
    validated = _validated_settings(request.settings)
    paper_db.set_trading_settings(validated, int(time.time() * 1000))
    return {"settings": validated}


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str):
    engine = _require_engine()
    trade = engine.close_position_by_id(position_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Open position or current market price not available")
    return {"closed": True, "trade": trade}
