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
        "signals": paper_engine.get_signals() if paper_engine is not None else [],
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


@router.post("/positions/{position_id}/close")
async def close_position(position_id: str):
    position = next((p for p in paper_db.list_positions() if str(p.get("id")) == position_id), None)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    if market_data_service is None:
        raise HTTPException(status_code=503, detail="Market data service unavailable")

    symbol = str(position["symbol"])
    state = market_data_service.symbol_states.get(symbol)
    if not state or float(state.current_price) <= 0:
        raise HTTPException(status_code=503, detail="Current market price unavailable")

    settings = dict(DEFAULT_TRADING_SETTINGS)
    settings.update(paper_db.get_trading_settings())
    side = str(position["side"])
    entry = float(position["entryPrice"])
    raw_price = float(state.current_price)
    quantity = float(position.get("quantity") or (float(position.get("size", 0)) / max(entry, 1e-9)))
    slippage = float(settings["slippagePct"]) / 100.0
    exit_price = raw_price * (1 - slippage if side == "BUY" else 1 + slippage)
    gross = (exit_price - entry) * quantity if side == "BUY" else (entry - exit_price) * quantity
    fee_rate = float(settings["feeRatePct"]) / 100.0
    fees = (entry * quantity + exit_price * quantity) * fee_rate
    realized = gross - fees
    capital = max(float(settings["capital"]), 1e-9)
    now = int(time.time() * 1000)

    trade = {
        "id": f"CLOSED-{position['id']}", "symbol": symbol, "side": side,
        "entryPrice": entry, "exitPrice": round(exit_price, 6),
        "size": float(position.get("size", entry * quantity)), "quantity": quantity,
        "leverage": float(position.get("leverage", 1)), "realizedPnL": round(realized, 2),
        "realizedPnLPercent": round((realized / capital) * 100.0, 3), "fees": round(fees, 2),
        "exitReason": "MANUAL", "openedAt": int(position["openedAt"]), "closedAt": now,
        "durationSeconds": max(0, (now - int(position["openedAt"])) // 1000), "isWin": realized > 0,
    }
    paper_db.save_closed_trade(trade)
    paper_db.delete_position(position_id)
    return {"closed": True, "trade": trade}


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
