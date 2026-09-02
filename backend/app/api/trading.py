import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import paper_db
from app.services.crypto_algo_engine import DEFAULT_TRADING_SETTINGS


router = APIRouter(prefix="/api/trading", tags=["trading"])
market_data_service = None
algo_engine = None


class EngineStateRequest(BaseModel):
    running: bool


class TradingSettingsRequest(BaseModel):
    settings: Dict[str, Any]


def _require_engine():
    if algo_engine is None:
        raise HTTPException(status_code=503, detail="Algo engine unavailable")
    return algo_engine


def _validated_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = dict(DEFAULT_TRADING_SETTINGS)
    saved = paper_db.get_trading_settings()
    if "minConfidence" in saved and "minSetupScore" not in saved:
        saved = {**saved, "minSetupScore": saved["minConfidence"]}
    current.update({key: value for key, value in saved.items() if key in current})
    current.update({key: value for key, value in payload.items() if key in current})

    current["capital"] = max(100.0, float(current["capital"]))
    current["riskPerTradePct"] = min(3.0, max(0.1, float(current["riskPerTradePct"])))
    current["maxDailyLossPct"] = min(10.0, max(0.5, float(current["maxDailyLossPct"])))
    current["maxPortfolioRiskPct"] = min(5.0, max(0.5, float(current["maxPortfolioRiskPct"])))
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
    current["breakevenAtR"] = min(3.0, max(0.5, float(current["breakevenAtR"])))
    current["trailingStartR"] = min(5.0, max(current["breakevenAtR"], float(current["trailingStartR"])))
    current["trailingDistanceR"] = min(3.0, max(0.25, float(current["trailingDistanceR"])))
    current["maxHoldMinutes"] = min(1440.0, max(5.0, float(current["maxHoldMinutes"])))
    current["minAtrPct"] = min(5.0, max(0.0, float(current["minAtrPct"])))
    current["maxAtrPct"] = min(20.0, max(current["minAtrPct"], float(current["maxAtrPct"])))
    current["minVolumeRatio"] = min(5.0, max(0.0, float(current["minVolumeRatio"])))
    current["btcTrendFilter"] = bool(current["btcTrendFilter"])
    current["feeRatePct"] = min(1.0, max(0.0, float(current["feeRatePct"])))
    current["slippagePct"] = min(1.0, max(0.0, float(current["slippagePct"])))
    current["maxEntryDriftPct"] = min(3.0, max(0.05, float(current["maxEntryDriftPct"])))
    return current


def _decorate_risk(risk: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    reason = None
    if float(risk.get("todayRealizedPnL", 0.0)) <= -float(risk.get("maxDailyLoss", 0.0)) and float(risk.get("maxDailyLoss", 0.0)) > 0:
        reason = "MAX_DAILY_LOSS"
    elif int(risk.get("consecutiveLosses", 0)) >= int(settings["maxConsecutiveLosses"]):
        reason = "MAX_CONSECUTIVE_LOSSES"
    elif int(risk.get("todayTrades", 0)) >= int(settings["maxTradesPerDay"]):
        reason = "MAX_TRADES_PER_DAY"
    elif int(risk.get("openPositions", 0)) >= int(settings["maxConcurrentTrades"]):
        reason = "MAX_CONCURRENT_TRADES"
    elif float(risk.get("openRisk", 0.0)) >= float(risk.get("maxPortfolioRisk", 0.0)) and float(risk.get("maxPortfolioRisk", 0.0)) > 0:
        reason = "MAX_PORTFOLIO_RISK"
    return {**risk, "blocked": reason is not None, "blockReason": reason}


@router.get("/state")
async def get_state():
    engine = _require_engine()
    state = engine.build_state()
    state["risk"] = _decorate_risk(state.get("risk", {}), state.get("settings", engine.get_settings()))
    return state


@router.get("/signals")
async def get_signals():
    engine = _require_engine()
    return {"strategy": engine.STRATEGY_VERSION, "signals": engine.get_signals()}


@router.get("/analysis")
async def get_analysis():
    engine = _require_engine()
    return {"strategy": engine.STRATEGY_VERSION, "analyses": engine.get_analyses()}


@router.get("/analysis/{symbol}")
async def get_symbol_analysis(symbol: str):
    engine = _require_engine()
    normalized = symbol.upper()
    if market_data_service is None or normalized not in market_data_service.symbol_states:
        raise HTTPException(status_code=404, detail="Symbol not available")
    analysis = engine.analyses.get(normalized) or engine.analyze_symbol(normalized)
    engine.analyses[normalized] = analysis
    return analysis


@router.get("/positions")
async def get_positions():
    return {"positions": list(_require_engine().positions_by_symbol.values())}


@router.get("/trades")
async def get_trades(limit: int = 200):
    safe_limit = min(1000, max(1, int(limit)))
    return {"trades": paper_db.list_closed_trades(safe_limit)}


@router.get("/risk")
async def get_risk():
    engine = _require_engine()
    return _decorate_risk(engine.get_risk_snapshot(), engine.get_settings())


@router.put("/engine")
async def set_engine_state(request: EngineStateRequest):
    engine = _require_engine()
    paper_db.set_engine_running(request.running, int(time.time() * 1000))
    if request.running:
        await engine.scan_all_symbols()
    return {
        "engine_running": paper_db.get_engine_running(),
        "mode": "PAPER_ONLY",
        "message": "Paper auto-execution armed" if request.running else "Paper auto-execution stopped",
    }


@router.put("/settings")
async def update_settings(request: TradingSettingsRequest):
    settings = _validated_settings(request.settings)
    paper_db.set_trading_settings(settings, int(time.time() * 1000))
    return {"settings": settings}


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str):
    trade = _require_engine().close_position_manually(position_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Position not found or current market price unavailable")
    return {"closed": True, "trade": trade}
