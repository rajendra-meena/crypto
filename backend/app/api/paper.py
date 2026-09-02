import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import paper_db
from app.services.paper_engine import DEFAULT_TRADING_SETTINGS


router = APIRouter(prefix="/api/paper", tags=["paper-trading"])


class EngineStateRequest(BaseModel):
    running: bool


class PositionRequest(BaseModel):
    position: Dict[str, Any]


class ClosedTradeRequest(BaseModel):
    trade: Dict[str, Any]


class ExecutedSignalRequest(BaseModel):
    signal_id: str
    symbol: str


class TradingSettingsRequest(BaseModel):
    settings: Dict[str, Any]


@router.get("/state")
async def get_paper_state():
    settings = dict(DEFAULT_TRADING_SETTINGS)
    settings.update(paper_db.get_trading_settings())
    return {
        "engine_running": paper_db.get_engine_running(),
        "positions": paper_db.list_positions(),
        "closed_trades": paper_db.list_closed_trades(),
        "executed_signal_ids": paper_db.list_executed_signal_ids(),
        "settings": settings,
    }


@router.put("/engine")
async def set_engine_state(request: EngineStateRequest):
    paper_db.set_engine_running(request.running, int(time.time() * 1000))
    return {"engine_running": request.running}


@router.put("/settings")
async def set_trading_settings(request: TradingSettingsRequest):
    current = dict(DEFAULT_TRADING_SETTINGS)
    current.update(paper_db.get_trading_settings())
    allowed = set(DEFAULT_TRADING_SETTINGS.keys())
    for key, value in request.settings.items():
        if key in allowed:
            current[key] = value

    # Safety bounds for paper engine configuration.
    current["capital"] = max(100.0, float(current["capital"]))
    current["riskPerTradePct"] = min(5.0, max(0.1, float(current["riskPerTradePct"])))
    current["maxDailyLossPct"] = min(20.0, max(0.5, float(current["maxDailyLossPct"])))
    current["maxConcurrentTrades"] = min(5, max(1, int(current["maxConcurrentTrades"])))
    current["maxLeverage"] = min(10.0, max(1.0, float(current["maxLeverage"])))
    current["minConfidence"] = min(95, max(60, int(current["minConfidence"])))
    current["maxTradesPerDay"] = min(50, max(1, int(current["maxTradesPerDay"])))
    current["maxConsecutiveLosses"] = min(10, max(1, int(current["maxConsecutiveLosses"])))
    current["cooldownMinutes"] = min(1440.0, max(0.0, float(current["cooldownMinutes"])))
    current["atrStopMultiplier"] = min(5.0, max(0.5, float(current["atrStopMultiplier"])))
    current["targetRR"] = min(5.0, max(1.0, float(current["targetRR"])))
    current["feeRatePct"] = min(1.0, max(0.0, float(current["feeRatePct"])))
    current["slippagePct"] = min(1.0, max(0.0, float(current["slippagePct"])))

    paper_db.set_trading_settings(current, int(time.time() * 1000))
    return {"settings": current}


@router.put("/positions/{position_id}")
async def save_position(position_id: str, request: PositionRequest):
    position = dict(request.position)
    if str(position.get("id", "")) != position_id:
        raise HTTPException(status_code=400, detail="Position id mismatch")
    paper_db.upsert_position(position)
    return {"saved": True, "id": position_id}


@router.delete("/positions/{position_id}")
async def delete_position(position_id: str):
    paper_db.delete_position(position_id)
    return {"deleted": True, "id": position_id}


@router.put("/closed-trades/{trade_id}")
async def save_closed_trade(trade_id: str, request: ClosedTradeRequest):
    trade = dict(request.trade)
    if str(trade.get("id", "")) != trade_id:
        raise HTTPException(status_code=400, detail="Trade id mismatch")
    paper_db.save_closed_trade(trade)
    return {"saved": True, "id": trade_id}


@router.put("/executed-signals/{signal_id}")
async def mark_executed_signal(signal_id: str, request: ExecutedSignalRequest):
    if request.signal_id != signal_id:
        raise HTTPException(status_code=400, detail="Signal id mismatch")
    paper_db.mark_signal_executed(signal_id, request.symbol, int(time.time() * 1000))
    return {"saved": True, "signal_id": signal_id}
