import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import paper_db


DEFAULT_TRADING_SETTINGS: Dict[str, Any] = {
    "capital": 10000.0,
    "riskPerTradePct": 1.0,
    "maxDailyLossPct": 3.0,
    "maxConcurrentTrades": 3,
    "maxLeverage": 3.0,
    "minConfidence": 72,
    "maxTradesPerDay": 8,
    "maxConsecutiveLosses": 3,
    "cooldownMinutes": 30,
    "atrStopMultiplier": 1.5,
    "targetRR": 2.0,
    "feeRatePct": 0.05,
    "slippagePct": 0.02,
}


def _ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    value = values[0]
    alpha = 2.0 / (period + 1.0)
    for item in values[1:]:
        value = item * alpha + value * (1.0 - alpha)
    return value


def _atr(candles: List[Any], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs: List[float] = []
    start = max(1, len(candles) - period)
    for idx in range(start, len(candles)):
        c = candles[idx]
        prev = candles[idx - 1]
        trs.append(max(
            float(c.high) - float(c.low),
            abs(float(c.high) - float(prev.close)),
            abs(float(c.low) - float(prev.close)),
        ))
    return sum(trs) / len(trs) if trs else 0.0


def _today_start_ms() -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000)


class PaperTradingEngine:
    """Backend-owned multi-symbol PAPER strategy, risk and execution engine."""

    def __init__(self, market_data_service: Any):
        self.market_data_service = market_data_service
        self.last_signal_candle: Dict[str, int] = {}

    def get_settings(self) -> Dict[str, Any]:
        saved = paper_db.get_trading_settings()
        merged = dict(DEFAULT_TRADING_SETTINGS)
        if saved:
            merged.update(saved)
        return merged

    def _series(self, symbol: str) -> Tuple[str, List[Any]]:
        state = self.market_data_service.symbol_states.get(symbol)
        if not state:
            return "1m", []
        for timeframe in ("15m", "5m", "1m"):
            candles = [c for c in state.get_candles(timeframe, 80) if getattr(c, "is_complete", False)]
            candles.sort(key=lambda c: c.timestamp)
            if len(candles) >= 25:
                return timeframe, candles
        candles = [c for c in state.get_candles("1m", 80) if getattr(c, "is_complete", False)]
        candles.sort(key=lambda c: c.timestamp)
        return "1m", candles

    def analyze_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        timeframe, candles = self._series(symbol)
        if len(candles) < 20:
            return None

        recent = candles[-30:]
        current = recent[-1]
        prior = recent[:-1]
        closes = [float(c.close) for c in recent]
        ema9 = _ema(closes, 9)
        ema20 = _ema(closes, 20)
        atr = _atr(recent, 14)
        if atr <= 0:
            return None

        resistance = max(float(c.high) for c in prior[-10:])
        support = min(float(c.low) for c in prior[-10:])
        bullish_breakout = float(current.close) > resistance
        bearish_breakdown = float(current.close) < support

        last6 = recent[-6:]
        bullish = sum(1 for c in last6 if float(c.close) > float(c.open))
        bearish = sum(1 for c in last6 if float(c.close) < float(c.open))
        move_pct = ((float(current.close) - float(last6[0].open)) / max(float(last6[0].open), 1e-9)) * 100.0

        volumes = [float(c.volume or 0) for c in prior[-20:]]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0.0
        volume_ratio = float(current.volume or 0) / avg_volume if avg_volume > 0 else 1.0

        score = 0
        reasons: List[str] = []
        if float(current.close) > ema9 > ema20:
            score += 2
            reasons.append("EMA trend up")
        elif float(current.close) < ema9 < ema20:
            score -= 2
            reasons.append("EMA trend down")
        if bullish_breakout:
            score += 3
            reasons.append("10-bar breakout")
        if bearish_breakdown:
            score -= 3
            reasons.append("10-bar breakdown")
        if bullish >= 4 and move_pct > 0:
            score += 1
            reasons.append("bullish candle momentum")
        if bearish >= 4 and move_pct < 0:
            score -= 1
            reasons.append("bearish candle momentum")
        if volume_ratio >= 1.30:
            if score > 0:
                score += 1
            elif score < 0:
                score -= 1
            reasons.append("volume confirmation")

        side: Optional[str] = "BUY" if score >= 4 else "SELL" if score <= -4 else None
        if not side:
            return None

        confidence = min(95, max(60, int(58 + abs(score) * 5 + (5 if volume_ratio >= 1.30 else 0))))
        return {
            "symbol": symbol,
            "side": side,
            "timeframe": timeframe,
            "candleTime": int(current.timestamp),
            "referencePrice": float(current.close),
            "atr": atr,
            "support": support,
            "resistance": resistance,
            "confidence": confidence,
            "score": score,
            "reason": " · ".join(reasons),
        }

    def _risk_blocked(self, symbol: str, settings: Dict[str, Any]) -> bool:
        positions = paper_db.list_positions()
        if any(str(p.get("symbol")) == symbol for p in positions):
            return True
        if len(positions) >= int(settings["maxConcurrentTrades"]):
            return True

        today = paper_db.list_closed_trades_since(_today_start_ms())
        if len(today) >= int(settings["maxTradesPerDay"]):
            return True

        realized = sum(float(t.get("realizedPnL", 0)) for t in today)
        max_daily_loss = float(settings["capital"]) * float(settings["maxDailyLossPct"]) / 100.0
        if realized <= -max_daily_loss:
            paper_db.set_engine_running(False, int(time.time() * 1000))
            return True

        consecutive_losses = 0
        for trade in today:
            if float(trade.get("realizedPnL", 0)) < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= int(settings["maxConsecutiveLosses"]):
            paper_db.set_engine_running(False, int(time.time() * 1000))
            return True

        cooldown_ms = int(float(settings["cooldownMinutes"]) * 60_000)
        last_closed = paper_db.get_last_closed_trade(symbol)
        if last_closed and int(time.time() * 1000) - int(last_closed.get("closedAt", 0)) < cooldown_ms:
            return True
        return False

    async def on_completed_candle(self, symbol: str) -> None:
        if not paper_db.get_engine_running():
            return
        settings = self.get_settings()
        signal = self.analyze_symbol(symbol)
        if not signal or signal["confidence"] < int(settings["minConfidence"]):
            return
        if self.last_signal_candle.get(symbol) == signal["candleTime"]:
            return
        if self._risk_blocked(symbol, settings):
            return

        state = self.market_data_service.symbol_states.get(symbol)
        if not state or state.current_price <= 0:
            return

        self.last_signal_candle[symbol] = signal["candleTime"]
        side = signal["side"]
        raw_price = float(state.current_price)
        slippage = float(settings["slippagePct"]) / 100.0
        entry = raw_price * (1 + slippage if side == "BUY" else 1 - slippage)

        stop_distance = max(signal["atr"] * float(settings["atrStopMultiplier"]), entry * 0.0025)
        stop = entry - stop_distance if side == "BUY" else entry + stop_distance
        target = entry + stop_distance * float(settings["targetRR"]) if side == "BUY" else entry - stop_distance * float(settings["targetRR"])

        risk_amount = float(settings["capital"]) * float(settings["riskPerTradePct"]) / 100.0
        quantity = risk_amount / max(stop_distance, 1e-9)
        notional = quantity * entry
        max_notional = float(settings["capital"]) * float(settings["maxLeverage"])
        if notional > max_notional:
            notional = max_notional
            quantity = notional / entry

        now = int(time.time() * 1000)
        signal_id = f"PA-{symbol}-{signal['timeframe']}-{signal['candleTime']}-{side}"
        if signal_id in paper_db.list_executed_signal_ids():
            return

        position = {
            "id": f"POS-{symbol}-{now}",
            "signalId": signal_id,
            "symbol": symbol,
            "side": side,
            "entryPrice": round(entry, 6),
            "currentPrice": round(raw_price, 6),
            "stopLoss": round(stop, 6),
            "target1": round(target, 6),
            "target2": round(target, 6),
            "leverage": float(settings["maxLeverage"]),
            "quantity": round(quantity, 8),
            "size": round(notional, 2),
            "margin": round(notional / max(float(settings["maxLeverage"]), 1.0), 2),
            "unrealizedPnL": 0.0,
            "unrealizedPnLPercent": 0.0,
            "openedAt": now,
            "confidence": signal["confidence"],
            "timeframe": signal["timeframe"],
            "reason": signal["reason"],
        }
        paper_db.upsert_position(position)
        paper_db.mark_signal_executed(signal_id, symbol, now)

    async def on_tick(self, symbol: str, price: float) -> None:
        position = next((p for p in paper_db.list_positions() if str(p.get("symbol")) == symbol), None)
        if not position:
            return

        settings = self.get_settings()
        side = str(position["side"])
        entry = float(position["entryPrice"])
        stop = float(position["stopLoss"])
        target = float(position["target1"])
        quantity = float(position.get("quantity") or (float(position.get("size", 0)) / max(entry, 1e-9)))

        gross = (price - entry) * quantity if side == "BUY" else (entry - price) * quantity
        entry_notional = entry * quantity
        exit_notional = price * quantity
        fee_rate = float(settings["feeRatePct"]) / 100.0
        estimated_fees = (entry_notional + exit_notional) * fee_rate
        unrealized = gross - estimated_fees
        capital = max(float(settings["capital"]), 1e-9)
        position["currentPrice"] = round(price, 6)
        position["unrealizedPnL"] = round(unrealized, 2)
        position["unrealizedPnLPercent"] = round((unrealized / capital) * 100.0, 3)
        position["lastUpdated"] = int(time.time() * 1000)
        paper_db.upsert_position(position)

        exit_reason: Optional[str] = None
        if side == "BUY" and price <= stop or side == "SELL" and price >= stop:
            exit_reason = "STOP_LOSS"
        elif side == "BUY" and price >= target or side == "SELL" and price <= target:
            exit_reason = "TARGET"
        if not exit_reason:
            return

        slippage = float(settings["slippagePct"]) / 100.0
        exit_price = price * (1 - slippage if side == "BUY" else 1 + slippage)
        gross_realized = (exit_price - entry) * quantity if side == "BUY" else (entry - exit_price) * quantity
        fees = (entry_notional + exit_price * quantity) * fee_rate
        realized = gross_realized - fees
        now = int(time.time() * 1000)
        trade = {
            "id": f"CLOSED-{position['id']}",
            "symbol": symbol,
            "side": side,
            "entryPrice": entry,
            "exitPrice": round(exit_price, 6),
            "size": float(position.get("size", entry_notional)),
            "quantity": quantity,
            "leverage": float(position.get("leverage", 1)),
            "realizedPnL": round(realized, 2),
            "realizedPnLPercent": round((realized / capital) * 100.0, 3),
            "fees": round(fees, 2),
            "exitReason": exit_reason,
            "openedAt": int(position["openedAt"]),
            "closedAt": now,
            "durationSeconds": max(0, (now - int(position["openedAt"])) // 1000),
            "isWin": realized > 0,
        }
        paper_db.save_closed_trade(trade)
        paper_db.delete_position(str(position["id"]))
