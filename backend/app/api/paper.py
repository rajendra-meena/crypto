import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import paper_db


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


@router.get("/state")
async def get_paper_state():
    return {
        "engine_running": paper_db.get_engine_running(),
        "positions": paper_db.list_positions(),
        "closed_trades": paper_db.list_closed_trades(),
        "executed_signal_ids": paper_db.list_executed_signal_ids(),
    }


@router.put("/engine")
async def set_engine_state(request: EngineStateRequest):
    paper_db.set_engine_running(request.running, int(time.time() * 1000))
    return {"engine_running": request.running}


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
