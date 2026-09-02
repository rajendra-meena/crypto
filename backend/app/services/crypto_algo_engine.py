import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import paper_db


DEFAULT_TRADING_SETTINGS: Dict[str, Any] = {
    "capital": 10000.0,
    "riskPerTradePct": 0.75,
    "maxDailyLossPct": 2.5,
    "maxPortfolioRiskPct": 1.5,
    "maxConcurrentTrades": 2,
    "maxLeverage": 3.0,
    "minSetupScore": 72,
    "maxTradesPerDay": 6,
    "maxConsecutiveLosses": 3,
    "cooldownMinutes": 20,
    "atrStopMultiplier": 1.30,
    "targetRR": 2.20,
    "feeRatePct": 0.05,
    "slippagePct": 0.02,
    "maxEntryDriftPct": 0.35,
    "minStopPct": 0.30,
    "maxStopPct": 1.80,
    "breakevenAtR": 1.00,
    "trailingStartR": 1.50,
    "trailingDistanceR": 0.75,
    "maxHoldMinutes": 240,
    "minAtrPct": 0.18,
    "maxAtrPct": 3.50,
}

TIMEFRAME_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000}


def _ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * alpha + result[-1] * (1.0 - alpha))
    return result


def _ema(values: List[float], period: int) -> float:
    series = _ema_series(values, period)
    return series[-1] if series else 0.0


def _rsi(values: List[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains = 0.0
    losses = 0.0
    for idx in range(len(values) - period, len(values)):
        diff = values[idx] - values[idx - 1]
        if diff >= 0:
            gains += diff
        else:
            losses += abs(diff)
    if losses == 0:
        return 100.0
    rs = (gains / period) / (losses / period)
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(candles: List[Any], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: List[float] = []
    start = max(1, len(candles) - period)
    for idx in range(start, len(candles)):
        current = candles[idx]
        previous = candles[idx - 1]
        true_ranges.append(max(
            float(current.high) - float(current.low),
            abs(float(current.high) - float(previous.close)),
            abs(float(current.low) - float(previous.close)),
        ))
    return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0


def _today_start_ms() -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000)


def _round_price(value: float) -> float:
    if value < 10:
        return round(value, 6)
    if value < 100:
        return round(value, 4)
    return round(value, 2)


class CryptoAlgoEngine:
    """Authoritative multi-timeframe PAPER trading engine.

    It never submits real exchange orders. All signal generation, risk checks,
    position lifecycle and persistence happen in the backend.
    """

    def __init__(self, market_data_service: Any):
        self.market_data_service = market_data_service
        self.analyses: Dict[str, Dict[str, Any]] = {}
        self.latest_signals: Dict[str, Dict[str, Any]] = {}

    def get_settings(self) -> Dict[str, Any]:
        merged = dict(DEFAULT_TRADING_SETTINGS)
        saved = paper_db.get_trading_settings()
        if saved:
            # Legacy compatibility: old minConfidence becomes minSetupScore.
            if "minConfidence" in saved and "minSetupScore" not in saved:
                saved = {**saved, "minSetupScore": saved["minConfidence"]}
            merged.update({k: v for k, v in saved.items() if k in merged})
        return merged

    def get_analyses(self) -> List[Dict[str, Any]]:
        return [self.analyses[s] for s in sorted(self.analyses.keys())]

    def get_signals(self) -> List[Dict[str, Any]]:
        return sorted(
            self.latest_signals.values(),
            key=lambda item: int(item.get("generatedAt", 0)),
            reverse=True,
        )[:20]

    def _completed(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        state = self.market_data_service.symbol_states.get(symbol)
        if not state:
            return []
        candles = [
            candle for candle in state.get_candles(timeframe, limit)
            if getattr(candle, "is_complete", False)
        ]
        candles.sort(key=lambda candle: int(candle.timestamp))
        return candles

    def _data_is_fresh(self, candles: List[Any], timeframe: str) -> bool:
        if not candles:
            return False
        max_age = TIMEFRAME_MS[timeframe] * 2.5
        return int(time.time() * 1000) - int(candles[-1].timestamp) <= max_age

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        base = {
            "symbol": symbol,
            "bias": "WAIT",
            "status": "WATCHING",
            "setupScore": 0,
            "timeframe": "15m/5m/1m",
            "trend": "NEUTRAL",
            "setup": "NONE",
            "trigger": "NONE",
            "rsi": 50.0,
            "atrPct": 0.0,
            "volumeRatio": 0.0,
            "support": 0.0,
            "resistance": 0.0,
            "reason": "Waiting for sufficient completed candles",
            "updatedAt": int(time.time() * 1000),
        }

        c15 = self._completed(symbol, "15m", 90)
        c5 = self._completed(symbol, "5m", 90)
        c1 = self._completed(symbol, "1m", 60)
        if len(c15) < 55 or len(c5) < 35 or len(c1) < 20:
            self.analyses[symbol] = base
            return base
        if not (self._data_is_fresh(c15, "15m") and self._data_is_fresh(c5, "5m") and self._data_is_fresh(c1, "1m")):
            stale = {**base, "reason": "Completed candle data is stale"}
            self.analyses[symbol] = stale
            return stale

        close15 = [float(c.close) for c in c15]
        close5 = [float(c.close) for c in c5]
        close1 = [float(c.close) for c in c1]
        ema20_15_series = _ema_series(close15, 20)
        ema50_15 = _ema(close15, 50)
        ema20_15 = ema20_15_series[-1]
        ema20_15_prev = ema20_15_series[-5]
        current15 = float(c15[-1].close)

        trend = "NEUTRAL"
        if current15 > ema20_15 > ema50_15 and ema20_15 > ema20_15_prev:
            trend = "BULLISH"
        elif current15 < ema20_15 < ema50_15 and ema20_15 < ema20_15_prev:
            trend = "BEARISH"

        current5 = c5[-1]
        previous5 = c5[-2]
        ema20_5 = _ema(close5, 20)
        prior20 = c5[-21:-1]
        resistance = max(float(c.high) for c in prior20)
        support = min(float(c.low) for c in prior20)
        breakout_up = float(current5.close) > resistance and float(current5.close) > float(previous5.high)
        breakout_down = float(current5.close) < support and float(current5.close) < float(previous5.low)
        pullback_long = (
            float(current5.low) <= ema20_5
            and float(current5.close) > ema20_5
            and float(current5.close) > float(current5.open)
        )
        pullback_short = (
            float(current5.high) >= ema20_5
            and float(current5.close) < ema20_5
            and float(current5.close) < float(current5.open)
        )

        setup = "NONE"
        if trend == "BULLISH" and breakout_up:
            setup = "BREAKOUT"
        elif trend == "BEARISH" and breakout_down:
            setup = "BREAKDOWN"
        elif trend == "BULLISH" and pullback_long:
            setup = "PULLBACK_RECLAIM"
        elif trend == "BEARISH" and pullback_short:
            setup = "PULLBACK_REJECT"

        ema9_1 = _ema(close1, 9)
        recent1 = c1[-3:]
        bullish_bodies = sum(1 for c in recent1 if float(c.close) > float(c.open))
        bearish_bodies = sum(1 for c in recent1 if float(c.close) < float(c.open))
        net1 = float(recent1[-1].close) - float(recent1[0].open)
        long_trigger = float(c1[-1].close) > ema9_1 and bullish_bodies >= 2 and net1 > 0
        short_trigger = float(c1[-1].close) < ema9_1 and bearish_bodies >= 2 and net1 < 0
        trigger = "LONG_CONFIRM" if long_trigger else "SHORT_CONFIRM" if short_trigger else "NONE"

        atr = _atr(c5, 14)
        price5 = max(float(current5.close), 1e-9)
        atr_pct = (atr / price5) * 100.0
        rsi = _rsi(close5, 14)
        prior_volumes = [float(c.volume or 0) for c in c5[-21:-1]]
        avg_volume = sum(prior_volumes) / len(prior_volumes) if prior_volumes else 0.0
        volume_ratio = float(current5.volume or 0) / avg_volume if avg_volume > 0 else 1.0

        settings = self.get_settings()
        volatility_ok = float(settings["minAtrPct"]) <= atr_pct <= float(settings["maxAtrPct"])
        side: Optional[str] = None
        if trend == "BULLISH" and setup in ("BREAKOUT", "PULLBACK_RECLAIM") and long_trigger:
            side = "BUY"
        elif trend == "BEARISH" and setup in ("BREAKDOWN", "PULLBACK_REJECT") and short_trigger:
            side = "SELL"

        score = 0
        reasons: List[str] = []
        if trend != "NEUTRAL":
            score += 30
            reasons.append(f"15m {trend.lower()} regime")
        if setup in ("BREAKOUT", "BREAKDOWN"):
            score += 25
            reasons.append(f"5m {setup.lower()}")
        elif setup != "NONE":
            score += 18
            reasons.append(f"5m {setup.lower().replace('_', ' ')}")
        if side:
            score += 15
            reasons.append("1m momentum confirmation")
        if volume_ratio >= 1.20:
            score += 10
            reasons.append("strong volume")
        elif volume_ratio >= 0.90:
            score += 5
            reasons.append("acceptable volume")
        rsi_ok = (side == "BUY" and 45 <= rsi <= 72) or (side == "SELL" and 28 <= rsi <= 55)
        if rsi_ok:
            score += 10
            reasons.append("RSI aligned")
        if volatility_ok:
            score += 10
            reasons.append("ATR regime valid")

        status = "WATCHING"
        bias = side or "WAIT"
        if side and score < int(settings["minSetupScore"]):
            status = "FILTERED"
            reasons.append("setup score below threshold")
        elif side and not volatility_ok:
            status = "FILTERED"
            reasons.append("volatility outside allowed regime")
        elif side:
            status = "READY"

        analysis = {
            **base,
            "bias": bias,
            "status": status,
            "setupScore": min(100, score),
            "trend": trend,
            "setup": setup,
            "trigger": trigger,
            "rsi": round(rsi, 1),
            "atrPct": round(atr_pct, 3),
            "volumeRatio": round(volume_ratio, 2),
            "support": _round_price(support),
            "resistance": _round_price(resistance),
            "reason": " · ".join(reasons) if reasons else "No aligned multi-timeframe setup",
            "setupCandleTime": int(current5.timestamp),
            "referencePrice": float(current5.close),
            "atr": atr,
            "updatedAt": int(time.time() * 1000),
        }
        self.analyses[symbol] = analysis
        return analysis

    def _risk_status(self, symbol: Optional[str] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        settings = self.get_settings()
        positions = paper_db.list_positions()
        today = paper_db.list_closed_trades_since(_today_start_ms())
        realized = sum(float(t.get("realizedPnL", 0)) for t in today)
        max_daily_loss = float(settings["capital"]) * float(settings["maxDailyLossPct"]) / 100.0

        consecutive_losses = 0
        for trade in today:
            if float(trade.get("realizedPnL", 0)) < 0:
                consecutive_losses += 1
            else:
                break

        open_risk = sum(float(p.get("initialRiskAmount", 0)) for p in positions)
        max_portfolio_risk = float(settings["capital"]) * float(settings["maxPortfolioRiskPct"]) / 100.0
        snapshot = {
            "todayTrades": len(today),
            "todayRealizedPnL": round(realized, 2),
            "consecutiveLosses": consecutive_losses,
            "openPositions": len(positions),
            "openRisk": round(open_risk, 2),
            "maxDailyLoss": round(max_daily_loss, 2),
            "maxPortfolioRisk": round(max_portfolio_risk, 2),
        }

        if realized <= -max_daily_loss:
            paper_db.set_engine_running(False, int(time.time() * 1000))
            return "MAX_DAILY_LOSS", snapshot
        if consecutive_losses >= int(settings["maxConsecutiveLosses"]):
            paper_db.set_engine_running(False, int(time.time() * 1000))
            return "MAX_CONSECUTIVE_LOSSES", snapshot
        if len(today) >= int(settings["maxTradesPerDay"]):
            return "MAX_TRADES_PER_DAY", snapshot
        if len(positions) >= int(settings["maxConcurrentTrades"]):
            return "MAX_CONCURRENT_TRADES", snapshot
        if symbol and any(str(p.get("symbol")) == symbol for p in positions):
            return "POSITION_ALREADY_OPEN", snapshot
        if open_risk >= max_portfolio_risk:
            return "MAX_PORTFOLIO_RISK", snapshot
        if symbol:
            cooldown_ms = int(float(settings["cooldownMinutes"]) * 60_000)
            last_closed = paper_db.get_last_closed_trade(symbol)
            if last_closed and int(time.time() * 1000) - int(last_closed.get("closedAt", 0)) < cooldown_ms:
                return "COOLDOWN", snapshot
        return None, snapshot

    def get_risk_snapshot(self) -> Dict[str, Any]:
        reason, snapshot = self._risk_status(None)
        return {**snapshot, "blocked": reason is not None, "blockReason": reason}

    async def scan_all_symbols(self) -> None:
        symbols = list(self.market_data_service.symbol_states.keys())
        for symbol in symbols:
            analysis = self.analyze_symbol(symbol)
            if paper_db.get_engine_running():
                await self._maybe_execute(symbol, analysis)

    async def on_completed_candle(self, symbol: str) -> None:
        analysis = self.analyze_symbol(symbol)
        if paper_db.get_engine_running():
            await self._maybe_execute(symbol, analysis)

    async def _maybe_execute(self, symbol: str, analysis: Dict[str, Any]) -> None:
        if analysis.get("status") not in ("READY", "FILTERED"):
            return

        settings = self.get_settings()
        side = str(analysis.get("bias"))
        setup_time = int(analysis.get("setupCandleTime") or 0)
        if side not in ("BUY", "SELL") or setup_time <= 0:
            return

        signal_id = f"MTF-{symbol}-5m-{setup_time}-{side}"
        state = self.market_data_service.symbol_states.get(symbol)
        if not state or float(state.current_price) <= 0:
            return

        raw_price = float(state.current_price)
        reference = max(float(analysis.get("referencePrice") or raw_price), 1e-9)
        entry_drift_pct = abs(raw_price - reference) / reference * 100.0

        block_reason: Optional[str] = None
        if int(analysis["setupScore"]) < int(settings["minSetupScore"]):
            block_reason = "MIN_SETUP_SCORE"
        elif entry_drift_pct > float(settings["maxEntryDriftPct"]):
            block_reason = "ENTRY_DRIFT"
        elif signal_id in paper_db.list_executed_signal_ids():
            block_reason = "ALREADY_EXECUTED"
        else:
            block_reason, _ = self._risk_status(symbol)

        slippage = float(settings["slippagePct"]) / 100.0
        entry = raw_price * (1 + slippage if side == "BUY" else 1 - slippage)
        atr = float(analysis.get("atr") or 0)
        c5 = self._completed(symbol, "5m", 20)
        swing_window = c5[-8:] if len(c5) >= 8 else c5
        if not swing_window or atr <= 0:
            return
        swing = min(float(c.low) for c in swing_window) if side == "BUY" else max(float(c.high) for c in swing_window)
        structural_distance = entry - swing if side == "BUY" else swing - entry
        min_distance = entry * float(settings["minStopPct"]) / 100.0
        atr_distance = atr * float(settings["atrStopMultiplier"])
        stop_distance = max(structural_distance, atr_distance, min_distance)
        stop_pct = stop_distance / max(entry, 1e-9) * 100.0
        if stop_pct > float(settings["maxStopPct"]):
            block_reason = block_reason or "STOP_TOO_WIDE"

        stop = entry - stop_distance if side == "BUY" else entry + stop_distance
        target = entry + stop_distance * float(settings["targetRR"]) if side == "BUY" else entry - stop_distance * float(settings["targetRR"])
        status = "BLOCKED" if block_reason else "READY"

        signal = {
            "id": signal_id,
            "symbol": symbol,
            "side": side,
            "timeframe": "15m/5m/1m",
            "entry": _round_price(entry),
            "stopLoss": _round_price(stop),
            "target1": _round_price(target),
            "target2": _round_price(target),
            "riskReward": f"1:{float(settings['targetRR']):g}",
            "confidence": int(analysis["setupScore"]),
            "generatedTime": datetime.fromtimestamp(setup_time / 1000, tz=timezone.utc).strftime("%H:%M:%S UTC"),
            "generatedAt": setup_time,
            "reason": analysis["reason"] + (f" · {block_reason}" if block_reason else ""),
            "status": status,
        }
        self.latest_signals[symbol] = signal
        if block_reason:
            return

        risk_amount = float(settings["capital"]) * float(settings["riskPerTradePct"]) / 100.0
        quantity = risk_amount / max(stop_distance, 1e-9)
        notional = quantity * entry
        max_notional = float(settings["capital"]) * float(settings["maxLeverage"])
        if notional > max_notional:
            notional = max_notional
            quantity = notional / entry
            risk_amount = quantity * stop_distance

        _, risk_snapshot = self._risk_status(symbol)
        if float(risk_snapshot["openRisk"]) + risk_amount > float(risk_snapshot["maxPortfolioRisk"]):
            self.latest_signals[symbol] = {**signal, "status": "BLOCKED", "reason": signal["reason"] + " · MAX_PORTFOLIO_RISK"}
            return

        now = int(time.time() * 1000)
        position = {
            "id": f"POS-{symbol}-{now}",
            "signalId": signal_id,
            "symbol": symbol,
            "side": side,
            "entryPrice": _round_price(entry),
            "currentPrice": _round_price(raw_price),
            "stopLoss": _round_price(stop),
            "initialStopLoss": _round_price(stop),
            "target1": _round_price(target),
            "target2": _round_price(target),
            "initialRisk": _round_price(stop_distance),
            "initialRiskAmount": round(risk_amount, 2),
            "leverage": float(settings["maxLeverage"]),
            "quantity": round(quantity, 8),
            "size": round(notional, 2),
            "margin": round(notional / max(float(settings["maxLeverage"]), 1.0), 2),
            "unrealizedPnL": 0.0,
            "unrealizedPnLPercent": 0.0,
            "rMultiple": 0.0,
            "managementStage": "INITIAL",
            "openedAt": now,
            "confidence": int(analysis["setupScore"]),
            "timeframe": "15m/5m/1m",
            "reason": analysis["reason"],
        }
        paper_db.upsert_position(position)
        paper_db.mark_signal_executed(signal_id, symbol, now)
        self.latest_signals[symbol] = {**signal, "status": "EXECUTED", "reason": signal["reason"] + " · AUTO PAPER ENTRY"}

    async def on_tick(self, symbol: str, price: float) -> None:
        position = next((p for p in paper_db.list_positions() if str(p.get("symbol")) == symbol), None)
        if not position:
            return

        settings = self.get_settings()
        side = str(position["side"])
        entry = float(position["entryPrice"])
        quantity = float(position.get("quantity") or (float(position.get("size", 0)) / max(entry, 1e-9)))
        initial_risk = max(float(position.get("initialRisk") or abs(entry - float(position["initialStopLoss"]))), 1e-9)
        move = price - entry if side == "BUY" else entry - price
        r_multiple = move / initial_risk

        stop = float(position["stopLoss"])
        if r_multiple >= float(settings["breakevenAtR"]):
            fee_buffer = entry * ((float(settings["feeRatePct"]) * 2 + float(settings["slippagePct"])) / 100.0)
            breakeven = entry + fee_buffer if side == "BUY" else entry - fee_buffer
            stop = max(stop, breakeven) if side == "BUY" else min(stop, breakeven)
            position["managementStage"] = "BREAKEVEN"

        if r_multiple >= float(settings["trailingStartR"]):
            trail_distance = initial_risk * float(settings["trailingDistanceR"])
            trail_stop = price - trail_distance if side == "BUY" else price + trail_distance
            stop = max(stop, trail_stop) if side == "BUY" else min(stop, trail_stop)
            position["managementStage"] = "TRAILING"

        position["stopLoss"] = _round_price(stop)
        position["currentPrice"] = _round_price(price)
        position["rMultiple"] = round(r_multiple, 2)
        position["lastUpdated"] = int(time.time() * 1000)

        gross = (price - entry) * quantity if side == "BUY" else (entry - price) * quantity
        fee_rate = float(settings["feeRatePct"]) / 100.0
        estimated_fees = (entry * quantity + price * quantity) * fee_rate
        unrealized = gross - estimated_fees
        capital = max(float(settings["capital"]), 1e-9)
        position["unrealizedPnL"] = round(unrealized, 2)
        position["unrealizedPnLPercent"] = round(unrealized / capital * 100.0, 3)
        paper_db.upsert_position(position)

        target = float(position["target1"])
        exit_reason: Optional[str] = None
        if (side == "BUY" and price <= stop) or (side == "SELL" and price >= stop):
            exit_reason = "TRAILING_STOP" if position.get("managementStage") == "TRAILING" else "STOP_LOSS"
        elif (side == "BUY" and price >= target) or (side == "SELL" and price <= target):
            exit_reason = "TARGET"
        else:
            held_minutes = (int(time.time() * 1000) - int(position["openedAt"])) / 60_000.0
            if held_minutes >= float(settings["maxHoldMinutes"]) and r_multiple < 0.50:
                exit_reason = "TIME_STOP"

        if exit_reason:
            self._close_position(position, price, exit_reason)

    def _close_position(self, position: Dict[str, Any], raw_price: float, reason: str) -> Dict[str, Any]:
        settings = self.get_settings()
        side = str(position["side"])
        entry = float(position["entryPrice"])
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
            "id": f"CLOSED-{position['id']}",
            "symbol": position["symbol"],
            "side": side,
            "entryPrice": entry,
            "exitPrice": _round_price(exit_price),
            "size": float(position.get("size", entry * quantity)),
            "quantity": quantity,
            "leverage": float(position.get("leverage", 1)),
            "realizedPnL": round(realized, 2),
            "realizedPnLPercent": round(realized / capital * 100.0, 3),
            "fees": round(fees, 2),
            "exitReason": reason,
            "openedAt": int(position["openedAt"]),
            "closedAt": now,
            "durationSeconds": max(0, (now - int(position["openedAt"])) // 1000),
            "isWin": realized > 0,
        }
        paper_db.save_closed_trade(trade)
        paper_db.delete_position(str(position["id"]))
        return trade

    def close_position_manually(self, position_id: str) -> Optional[Dict[str, Any]]:
        position = next((p for p in paper_db.list_positions() if str(p.get("id")) == position_id), None)
        if not position:
            return None
        state = self.market_data_service.symbol_states.get(str(position["symbol"]))
        if not state or float(state.current_price) <= 0:
            return None
        return self._close_position(position, float(state.current_price), "MANUAL")
