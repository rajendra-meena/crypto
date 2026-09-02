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


def _validated_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    current = dict(DEFAULT_TRADING_SETTINGS)
    saved = paper_db.get_trading_settings()
    if "minConfidence" in saved and "minSetupScore" not in saved:
        saved = {**saved, "minSetupScore": saved["minConfidence"]}
    current.update({k: v for k, v in saved.items() if k in current})
    current.update({k: v for k, v in payload.items() if k in current})

    current["capital"] = max(100.0, float(current["capital"]))
    current["riskPerTradePct"] = min(3.0, max(0.1, float(current["riskPerTradePct"])))
    current["maxDailyLossPct"] = min(10.0, max(0.5, float(current["maxDailyLossPct"])))
    current["maxPortfolioRiskPct"] = min(5.0, max(0.5, float(current["maxPortfolioRiskPct"])))
    current["maxConcurrentTrades"] = min(5, max(1, int(current["maxConcurrentTrades"])))
    current["maxLeverage"] = min(10.0, max(1.0, float(current["maxLeverage"])))
    current["minSetupScore"] = min(95, max(60, int(current["minSetupScore"])))
    current["maxTradesPerDay"] = min(30, max(1, int(current["maxTradesPerDay"])))
    current["maxConsecutiveLosses"] = min(10, max(1, int(current["maxConsecutiveLosses"])))
    current["cooldownMinutes"] = min(1440.0, max(0.0, float(current["cooldownMinutes"])))
    current["atrStopMultiplier"] = min(4.0, max(0.5, float(current["atrStopMultiplier"])))
    current["targetRR"] = min(5.0, max(1.2, float(current["targetRR"])))
    current["feeRatePct"] = min(1.0, max(0.0, float(current["feeRatePct"])))
    current["slippagePct"] = min(1.0, max(0.0, float(current["slippagePct"])))
    current["maxEntryDriftPct"] = min(3.0, max(0.05, float(current["maxEntryDriftPct"])))
    current["minStopPct"] = min(2.0, max(0.05, float(current["minStopPct"])))
    current["maxStopPct"] = min(8.0, max(current["minStopPct"], float(current["maxStopPct"])))
    current["breakevenAtR"] = min(3.0, max(0.5, float(current["breakevenAtR"])))
    current["trailingStartR"] = min(5.0, max(current["breakevenAtR"], float(current["trailingStartR"])))
    current["trailingDistanceR"] = min(2.0, max(0.25, float(current["trailingDistanceR"])))
    current["maxHoldMinutes"] = min(1440, max(15, int(current["maxHoldMinutes"])))
    current["minAtrPct"] = min(5.0, max(0.01, float(current["minAtrPct"])))
    current["maxAtrPct"] = min(20.0, max(current["minAtrPct"], float(current["maxAtrPct"])))
    return current


@router.get("/state")
async def get_state():
    settings = _validated_settings({})
    analyses = algo_engine.get_analyses() if algo_engine else []
    signals = algo_engine.get_signals() if algo_engine else []
    risk = algo_engine.get_risk_snapshot() if algo_engine else {}
    return {
        "engine_running": paper_db.get_engine_running(),
        "mode": "PAPER",
        "strategy": "MTF_PRICE_ACTION_V1",
        "positions": paper_db.list_positions(),
        "closed_trades": paper_db.list_closed_trades(),
        "executed_signal_ids": paper_db.list_executed_signal_ids(),
        "analyses": analyses,
        "signals": signals,
        "risk": risk,
        "settings": settings,
    }


@router.get("/analysis/{symbol}")
async def get_symbol_analysis(symbol: str):
    if algo_engine is None:
        raise HTTPException(status_code=503, detail="Algo engine unavailable")
    symbol = symbol.upper()
    analysis = algo_engine.analyses.get(symbol) or algo_engine.analyze_symbol(symbol)
    if not analysis or symbol not in market_data_service.symbol_states:
        raise HTTPException(status_code=404, detail="Symbol not available")
    return analysis


@router.put("/engine")
async def set_engine_state(request: EngineStateRequest):
    paper_db.set_engine_running(request.running, int(time.time() * 1000))
    if request.running and algo_engine is not None:
        await algo_engine.scan_all_symbols()
    return {"engine_running": paper_db.get_engine_running()}


@router.put("/settings")
async def update_settings(request: TradingSettingsRequest):
    settings = _validated_settings(request.settings)
    paper_db.set_trading_settings(settings, int(time.time() * 1000))
    return {"settings": settings}


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str):
    if algo_engine is None:
        raise HTTPException(status_code=503, detail="Algo engine unavailable")
    trade = algo_engine.close_position_manually(position_id)
    if trade is None:
        raise HTTPException(status_code=404, detail="Position not found or current market price unavailable")
    return {"closed": True, "trade": trade}
