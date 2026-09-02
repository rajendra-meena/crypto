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
    "maxSameDirection": 2,
    "maxLeverage": 3.0,
    "minSetupScore": 70,
    "maxTradesPerDay": 6,
    "maxConsecutiveLosses": 3,
    "cooldownMinutes": 20,
    "atrStopMultiplier": 1.4,
    "minStopPct": 0.25,
    "maxStopPct": 1.50,
    "targetRR": 2.0,
    "breakevenAtR": 1.0,
    "trailingStartR": 1.5,
    "trailingDistanceR": 0.75,
    "maxHoldMinutes": 240,
    "minAtrPct": 0.03,
    "maxAtrPct": 2.50,
    "minVolumeRatio": 1.10,
    "btcTrendFilter": True,
    "feeRatePct": 0.05,
    "slippagePct": 0.02,
    "maxEntryDriftPct": 0.35,
}

TIMEFRAME_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_start_ms() -> int:
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000)


def _ema_series(values: List[float], period: int) -> List[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * alpha + result[-1] * (1.0 - alpha))
    return result


def _rsi(values: List[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains = 0.0
    losses = 0.0
    start = len(values) - period
    for idx in range(start, len(values)):
        diff = values[idx] - values[idx - 1]
        if diff >= 0:
            gains += diff
        else:
            losses += abs(diff)
    if losses == 0:
        return 100.0
    rs = (gains / period) / max(losses / period, 1e-12)
    return 100.0 - 100.0 / (1.0 + rs)


def _atr(candles: List[Any], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    values: List[float] = []
    start = max(1, len(candles) - period)
    for idx in range(start, len(candles)):
        current = candles[idx]
        previous = candles[idx - 1]
        values.append(
            max(
                float(current.high) - float(current.low),
                abs(float(current.high) - float(previous.close)),
                abs(float(current.low) - float(previous.close)),
            )
        )
    return sum(values) / len(values) if values else 0.0


def _round_price(value: float) -> float:
    if value < 10:
        return round(value, 6)
    if value < 100:
        return round(value, 4)
    return round(value, 2)


class CryptoAlgoEngine:
    """Backend-authoritative 15m/5m/1m PAPER crypto strategy.

    15m defines market regime, 5m defines setup/trend quality and 1m completed
    candle provides the execution trigger. This engine never submits live orders.
    """

    STRATEGY_VERSION = "MTPA_3TF_V2"

    def __init__(self, market_data_service: Any):
        self.market_data_service = market_data_service
        self.analyses: Dict[str, Dict[str, Any]] = {}
        self.latest_signals: Dict[str, Dict[str, Any]] = {}
        self.last_evaluated_trigger: Dict[str, int] = {}
        self.positions_by_symbol: Dict[str, Dict[str, Any]] = {
            str(position.get("symbol")): position for position in paper_db.list_positions()
        }
        self.last_position_persist_ms: Dict[str, int] = {}
        self.last_scan_ms = 0

    def get_settings(self) -> Dict[str, Any]:
        settings = dict(DEFAULT_TRADING_SETTINGS)
        saved = paper_db.get_trading_settings()
        if saved:
            if "minConfidence" in saved and "minSetupScore" not in saved:
                saved = {**saved, "minSetupScore": saved["minConfidence"]}
            settings.update({key: value for key, value in saved.items() if key in settings})
        return settings

    def get_analyses(self) -> List[Dict[str, Any]]:
        return [self.analyses[key] for key in sorted(self.analyses.keys())]

    def get_signals(self) -> List[Dict[str, Any]]:
        values = list(self.latest_signals.values())
        values.sort(key=lambda item: int(item.get("generatedAt", 0)), reverse=True)
        return values[:20]

    def get_risk_snapshot(self) -> Dict[str, Any]:
        settings = self.get_settings()
        today = paper_db.list_closed_trades_since(_today_start_ms())
        realized = sum(float(item.get("realizedPnL", 0.0)) for item in today)
        consecutive_losses = 0
        for trade in today:
            if float(trade.get("realizedPnL", 0.0)) < 0:
                consecutive_losses += 1
            else:
                break
        open_risk = sum(float(position.get("initialRiskAmount", 0.0)) for position in self.positions_by_symbol.values())
        max_daily_loss = float(settings["capital"]) * float(settings["maxDailyLossPct"]) / 100.0
        max_portfolio_risk = float(settings["capital"]) * float(settings["maxPortfolioRiskPct"]) / 100.0
        return {
            "todayTrades": len(today),
            "todayRealizedPnL": round(realized, 2),
            "consecutiveLosses": consecutive_losses,
            "openPositions": len(self.positions_by_symbol),
            "openRisk": round(open_risk, 2),
            "maxDailyLoss": round(max_daily_loss, 2),
            "dailyLossRemaining": round(max(0.0, max_daily_loss + realized), 2),
            "maxPortfolioRisk": round(max_portfolio_risk, 2),
            "engineRunning": paper_db.get_engine_running(),
            "lastScan": self.last_scan_ms,
        }

    def build_state(self) -> Dict[str, Any]:
        return {
            "engine_running": paper_db.get_engine_running(),
            "mode": "PAPER_ONLY",
            "strategy": self.STRATEGY_VERSION,
            "scanner": {
                "status": "ACTIVE",
                "lastScan": self.last_scan_ms,
                "symbols": sorted(self.market_data_service.symbol_states.keys()),
            },
            "positions": list(self.positions_by_symbol.values()),
            "closed_trades": paper_db.list_closed_trades(),
            "executed_signal_ids": paper_db.list_executed_signal_ids(),
            "analyses": self.get_analyses(),
            "signals": self.get_signals(),
            "risk": self.get_risk_snapshot(),
            "settings": self.get_settings(),
        }

    def _completed(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        state = self.market_data_service.symbol_states.get(symbol)
        if not state:
            return []
        raw = [
            candle
            for candle in state.get_candles(timeframe, limit + 15)
            if bool(getattr(candle, "is_complete", False))
        ]
        by_timestamp: Dict[int, Any] = {int(candle.timestamp): candle for candle in raw}
        return [by_timestamp[key] for key in sorted(by_timestamp.keys())][-limit:]

    def _is_fresh(self, candles: List[Any], timeframe: str) -> bool:
        if not candles:
            return False
        return _now_ms() - int(candles[-1].timestamp) <= TIMEFRAME_MS[timeframe] * 2.5

    def _htf_direction(self, symbol: str) -> str:
        candles = self._completed(symbol, "15m", 60)
        if len(candles) < 55:
            return "NEUTRAL"
        closes = [float(candle.close) for candle in candles]
        ema20 = _ema_series(closes, 20)
        ema50 = _ema_series(closes, 50)
        slope = ema20[-1] - ema20[-6]
        if closes[-1] > ema20[-1] > ema50[-1] and slope > 0:
            return "BULLISH"
        if closes[-1] < ema20[-1] < ema50[-1] and slope < 0:
            return "BEARISH"
        return "NEUTRAL"

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        now = _now_ms()
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
            "bodyQuality": 0.0,
            "support": 0.0,
            "resistance": 0.0,
            "blockers": [],
            "reason": "Waiting for enough completed candles",
            "triggerCandleTime": 0,
            "referencePrice": 0.0,
            "atr": 0.0,
            "updatedAt": now,
        }

        c15 = self._completed(symbol, "15m", 60)
        c5 = self._completed(symbol, "5m", 50)
        c1 = self._completed(symbol, "1m", 40)
        if len(c15) < 55 or len(c5) < 30 or len(c1) < 25:
            return base
        if not (self._is_fresh(c15, "15m") and self._is_fresh(c5, "5m") and self._is_fresh(c1, "1m")):
            return {**base, "status": "BLOCKED", "blockers": ["STALE_COMPLETED_CANDLES"], "reason": "Completed candle data is stale"}

        close15 = [float(c.close) for c in c15]
        ema20_15 = _ema_series(close15, 20)
        ema50_15 = _ema_series(close15, 50)
        trend = "NEUTRAL"
        if close15[-1] > ema20_15[-1] > ema50_15[-1] and ema20_15[-1] > ema20_15[-6]:
            trend = "BULLISH"
        elif close15[-1] < ema20_15[-1] < ema50_15[-1] and ema20_15[-1] < ema20_15[-6]:
            trend = "BEARISH"

        close5 = [float(c.close) for c in c5]
        ema9_5 = _ema_series(close5, 9)
        ema21_5 = _ema_series(close5, 21)
        mtf = "NEUTRAL"
        if close5[-1] > ema9_5[-1] > ema21_5[-1]:
            mtf = "BULLISH"
        elif close5[-1] < ema9_5[-1] < ema21_5[-1]:
            mtf = "BEARISH"

        direction = "WAIT"
        if trend == "BULLISH" and mtf == "BULLISH":
            direction = "BUY"
        elif trend == "BEARISH" and mtf == "BEARISH":
            direction = "SELL"

        current1 = c1[-1]
        prior1 = c1[-7:-1]
        prior_high = max(float(c.high) for c in prior1)
        prior_low = min(float(c.low) for c in prior1)
        bullish_breakout = float(current1.close) > prior_high
        bearish_breakout = float(current1.close) < prior_low
        breakout_ok = bullish_breakout if direction == "BUY" else bearish_breakout if direction == "SELL" else False

        current5 = c5[-1]
        support = min(float(c.low) for c in c5[-10:])
        resistance = max(float(c.high) for c in c5[-10:])
        atr = _atr(c5, 14)
        atr_pct = atr / max(float(current5.close), 1e-12) * 100.0
        rsi = _rsi(close5, 14)

        prior_volumes = [float(c.volume or 0.0) for c in c1[-21:-1]]
        average_volume = sum(prior_volumes) / len(prior_volumes) if prior_volumes else 0.0
        volume_ratio = float(current1.volume or 0.0) / average_volume if average_volume > 0 else 0.0

        candle_range = max(float(current1.high) - float(current1.low), 1e-12)
        body_quality = abs(float(current1.close) - float(current1.open)) / candle_range
        directional_body = (
            direction == "BUY" and float(current1.close) > float(current1.open)
        ) or (
            direction == "SELL" and float(current1.close) < float(current1.open)
        )

        settings = self.get_settings()
        blockers: List[str] = []
        reasons: List[str] = []
        score = 0

        if direction != "WAIT":
            score += 20
            reasons.append("15m regime aligned")
            score += 15
            reasons.append("5m EMA trend aligned")
        else:
            blockers.append("TIMEFRAME_TREND_NOT_ALIGNED")

        if breakout_ok:
            score += 25
            reasons.append("1m completed-candle breakout")
        else:
            blockers.append("NO_COMPLETED_1M_BREAKOUT")

        rsi_ok = (52.0 <= rsi <= 72.0) if direction == "BUY" else (28.0 <= rsi <= 48.0) if direction == "SELL" else False
        if rsi_ok:
            score += 10
            reasons.append("5m RSI confirms momentum")
        elif direction != "WAIT":
            blockers.append("RSI_NOT_CONFIRMING")

        if volume_ratio >= float(settings["minVolumeRatio"]):
            score += 10
            reasons.append("1m volume expansion")
        else:
            blockers.append("LOW_TRIGGER_VOLUME")

        volatility_ok = float(settings["minAtrPct"]) <= atr_pct <= float(settings["maxAtrPct"])
        if volatility_ok:
            score += 10
            reasons.append("5m ATR regime valid")
        else:
            blockers.append("VOLATILITY_OUT_OF_RANGE")

        if body_quality >= 0.55 and directional_body:
            score += 10
            reasons.append("strong trigger candle body")
        else:
            blockers.append("WEAK_TRIGGER_CANDLE")

        if atr > 0 and abs(close5[-1] - ema21_5[-1]) / atr > 2.5:
            blockers.append("OVEREXTENDED_FROM_5M_MEAN")

        if bool(settings.get("btcTrendFilter", True)) and symbol != "BTCUSDT" and direction != "WAIT":
            btc_direction = self._htf_direction("BTCUSDT")
            if (direction == "BUY" and btc_direction == "BEARISH") or (direction == "SELL" and btc_direction == "BULLISH"):
                blockers.append("BTC_REGIME_CONFLICT")

        hard_blockers = {
            "TIMEFRAME_TREND_NOT_ALIGNED",
            "NO_COMPLETED_1M_BREAKOUT",
            "VOLATILITY_OUT_OF_RANGE",
            "OVEREXTENDED_FROM_5M_MEAN",
            "BTC_REGIME_CONFLICT",
        }
        hard_blocked = any(item in hard_blockers for item in blockers)
        ready = direction != "WAIT" and score >= int(settings["minSetupScore"]) and not hard_blocked
        status = "READY" if ready else "FILTERED" if direction != "WAIT" else "WATCHING"
        setup = "BREAKOUT" if direction == "BUY" and bullish_breakout else "BREAKDOWN" if direction == "SELL" and bearish_breakout else "NONE"
        trigger = "LONG_CONFIRM" if direction == "BUY" and breakout_ok else "SHORT_CONFIRM" if direction == "SELL" and breakout_ok else "NONE"
        reason = " · ".join(reasons) if reasons else "Waiting for multi-timeframe alignment"
        if blockers:
            reason += " | " + ", ".join(blockers)

        return {
            **base,
            "bias": direction,
            "status": status,
            "setupScore": min(100, score),
            "trend": trend,
            "mtfTrend": mtf,
            "setup": setup,
            "trigger": trigger,
            "rsi": round(rsi, 1),
            "atrPct": round(atr_pct, 3),
            "volumeRatio": round(volume_ratio, 2),
            "bodyQuality": round(body_quality, 2),
            "support": _round_price(support),
            "resistance": _round_price(resistance),
            "blockers": blockers,
            "reason": reason,
            "triggerCandleTime": int(current1.timestamp),
            "referencePrice": float(current1.close),
            "atr": atr,
            "updatedAt": now,
        }

    def _risk_status(self, symbol: str, side: str) -> Tuple[Optional[str], Dict[str, Any]]:
        settings = self.get_settings()
        risk = self.get_risk_snapshot()
        if float(risk["todayRealizedPnL"]) <= -float(risk["maxDailyLoss"]):
            paper_db.set_engine_running(False, _now_ms())
            return "MAX_DAILY_LOSS", risk
        if int(risk["consecutiveLosses"]) >= int(settings["maxConsecutiveLosses"]):
            paper_db.set_engine_running(False, _now_ms())
            return "MAX_CONSECUTIVE_LOSSES", risk
        if int(risk["todayTrades"]) >= int(settings["maxTradesPerDay"]):
            return "MAX_TRADES_PER_DAY", risk
        if len(self.positions_by_symbol) >= int(settings["maxConcurrentTrades"]):
            return "MAX_CONCURRENT_TRADES", risk
        if symbol in self.positions_by_symbol:
            return "POSITION_ALREADY_OPEN", risk
        same_direction = sum(1 for position in self.positions_by_symbol.values() if str(position.get("side")) == side)
        if same_direction >= int(settings["maxSameDirection"]):
            return "MAX_SAME_DIRECTION_EXPOSURE", risk
        if float(risk["openRisk"]) >= float(risk["maxPortfolioRisk"]):
            return "MAX_PORTFOLIO_RISK", risk
        last_closed = paper_db.get_last_closed_trade(symbol)
        cooldown_ms = int(float(settings["cooldownMinutes"]) * 60_000)
        if last_closed and _now_ms() - int(last_closed.get("closedAt", 0)) < cooldown_ms:
            return "COOLDOWN", risk
        return None, risk

    def _make_signal(self, analysis: Dict[str, Any], status: str, suffix: Optional[str] = None) -> Dict[str, Any]:
        settings = self.get_settings()
        symbol = str(analysis["symbol"])
        side = str(analysis["bias"])
        state = self.market_data_service.symbol_states.get(symbol)
        raw_price = float(state.current_price) if state else 0.0
        slippage = float(settings["slippagePct"]) / 100.0
        entry = raw_price * (1.0 + slippage if side == "BUY" else 1.0 - slippage)

        atr_distance = float(analysis["atr"]) * float(settings["atrStopMultiplier"])
        min_distance = raw_price * float(settings["minStopPct"]) / 100.0
        structure_distance = raw_price - float(analysis["support"]) if side == "BUY" else float(analysis["resistance"]) - raw_price
        stop_distance = max(atr_distance, min_distance, structure_distance if structure_distance > 0 else 0.0)
        max_distance = raw_price * float(settings["maxStopPct"]) / 100.0
        final_status = status
        final_suffix = suffix
        if max_distance > 0 and stop_distance > max_distance:
            final_status = "FILTERED"
            final_suffix = "STOP_TOO_WIDE"

        stop = entry - stop_distance if side == "BUY" else entry + stop_distance
        target = entry + stop_distance * float(settings["targetRR"]) if side == "BUY" else entry - stop_distance * float(settings["targetRR"])
        signal_id = f"{self.STRATEGY_VERSION}-{symbol}-{analysis['triggerCandleTime']}-{side}"
        reason = str(analysis["reason"])
        if final_suffix:
            reason += f" | {final_suffix}"

        return {
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
            "setupScore": int(analysis["setupScore"]),
            "generatedTime": datetime.fromtimestamp(int(analysis["triggerCandleTime"]) / 1000, tz=timezone.utc).strftime("%H:%M:%S UTC"),
            "generatedAt": int(analysis["triggerCandleTime"]),
            "reason": reason,
            "status": final_status,
            "initialRisk": _round_price(stop_distance),
        }

    async def scan_all_symbols(self) -> None:
        self.last_scan_ms = _now_ms()
        for symbol in list(self.market_data_service.symbol_states.keys()):
            await self.evaluate_symbol(symbol)

    async def on_completed_candle(self, symbol: str) -> None:
        await self.evaluate_symbol(symbol)

    async def evaluate_symbol(self, symbol: str) -> None:
        analysis = self.analyze_symbol(symbol)
        self.analyses[symbol] = analysis
        trigger_time = int(analysis.get("triggerCandleTime", 0))
        if trigger_time <= 0:
            self.latest_signals.pop(symbol, None)
            return
        if self.last_evaluated_trigger.get(symbol) == trigger_time:
            return
        self.last_evaluated_trigger[symbol] = trigger_time

        if analysis["status"] != "READY" or analysis["bias"] == "WAIT":
            self.latest_signals.pop(symbol, None)
            return

        if not paper_db.get_engine_running():
            self.latest_signals[symbol] = self._make_signal(analysis, "BLOCKED", "ENGINE_OFF")
            return

        state = self.market_data_service.symbol_states.get(symbol)
        if not state or float(state.current_price) <= 0:
            self.latest_signals[symbol] = self._make_signal(analysis, "BLOCKED", "NO_LIVE_PRICE")
            return

        reference = float(analysis["referencePrice"])
        drift_pct = abs(float(state.current_price) - reference) / max(reference, 1e-12) * 100.0
        if drift_pct > float(self.get_settings()["maxEntryDriftPct"]):
            self.latest_signals[symbol] = self._make_signal(analysis, "FILTERED", "ENTRY_DRIFT_TOO_LARGE")
            return

        block_reason, risk_snapshot = self._risk_status(symbol, str(analysis["bias"]))
        signal = self._make_signal(analysis, "READY", block_reason)
        if block_reason:
            signal["status"] = "BLOCKED"
            self.latest_signals[symbol] = signal
            return
        if signal["status"] == "FILTERED":
            self.latest_signals[symbol] = signal
            return

        signal_id = str(signal["id"])
        if signal_id in paper_db.list_executed_signal_ids():
            signal["status"] = "EXECUTED"
            self.latest_signals[symbol] = signal
            return

        settings = self.get_settings()
        entry = float(signal["entry"])
        stop = float(signal["stopLoss"])
        initial_risk = abs(entry - stop)
        if initial_risk <= 0:
            signal["status"] = "FILTERED"
            signal["reason"] += " | INVALID_STOP_DISTANCE"
            self.latest_signals[symbol] = signal
            return

        requested_risk = float(settings["capital"]) * float(settings["riskPerTradePct"]) / 100.0
        remaining_portfolio_risk = max(0.0, float(risk_snapshot["maxPortfolioRisk"]) - float(risk_snapshot["openRisk"]))
        risk_amount = min(requested_risk, remaining_portfolio_risk)
        if risk_amount <= 0:
            signal["status"] = "BLOCKED"
            signal["reason"] += " | MAX_PORTFOLIO_RISK"
            self.latest_signals[symbol] = signal
            return

        quantity = risk_amount / initial_risk
        notional = quantity * entry
        max_notional = float(settings["capital"]) * float(settings["maxLeverage"])
        if notional > max_notional:
            notional = max_notional
            quantity = notional / max(entry, 1e-12)
        actual_risk_amount = initial_risk * quantity

        now = _now_ms()
        position = {
            "id": f"POS-{symbol}-{now}",
            "signalId": signal_id,
            "strategyVersion": self.STRATEGY_VERSION,
            "symbol": symbol,
            "side": analysis["bias"],
            "entryPrice": entry,
            "currentPrice": float(state.current_price),
            "stopLoss": stop,
            "initialStopLoss": stop,
            "target1": float(signal["target1"]),
            "target2": float(signal["target2"]),
            "initialRisk": _round_price(initial_risk),
            "initialRiskAmount": round(actual_risk_amount, 2),
            "atrAtEntry": float(analysis["atr"]),
            "leverage": float(settings["maxLeverage"]),
            "quantity": round(quantity, 8),
            "size": round(notional, 2),
            "margin": round(notional / max(float(settings["maxLeverage"]), 1.0), 2),
            "unrealizedPnL": 0.0,
            "unrealizedPnLPercent": 0.0,
            "rMultiple": 0.0,
            "breakEvenActivated": False,
            "trailingActivated": False,
            "openedAt": now,
            "lastUpdated": now,
            "setupScore": int(analysis["setupScore"]),
            "reason": analysis["reason"],
        }
        self.positions_by_symbol[symbol] = position
        paper_db.upsert_position(position)
        paper_db.mark_signal_executed(signal_id, symbol, now)
        signal["status"] = "EXECUTED"
        self.latest_signals[symbol] = signal

    def _close_position(self, symbol: str, raw_price: float, reason: str) -> Optional[Dict[str, Any]]:
        position = self.positions_by_symbol.get(symbol)
        if not position:
            return None
        settings = self.get_settings()
        side = str(position["side"])
        entry = float(position["entryPrice"])
        quantity = float(position.get("quantity", 0.0))
        slippage = float(settings["slippagePct"]) / 100.0
        exit_price = raw_price * (1.0 - slippage if side == "BUY" else 1.0 + slippage)
        gross = (exit_price - entry) * quantity if side == "BUY" else (entry - exit_price) * quantity
        fee_rate = float(settings["feeRatePct"]) / 100.0
        fees = (entry * quantity + exit_price * quantity) * fee_rate
        realized = gross - fees
        initial_risk_amount = max(float(position.get("initialRiskAmount", 0.0)), 1e-12)
        capital = max(float(settings["capital"]), 1e-12)
        now = _now_ms()
        trade = {
            "id": f"CLOSED-{position['id']}",
            "signalId": position.get("signalId"),
            "strategyVersion": position.get("strategyVersion", self.STRATEGY_VERSION),
            "symbol": symbol,
            "side": side,
            "entryPrice": entry,
            "exitPrice": _round_price(exit_price),
            "size": float(position.get("size", entry * quantity)),
            "quantity": quantity,
            "leverage": float(position.get("leverage", 1.0)),
            "realizedPnL": round(realized, 2),
            "realizedPnLPercent": round(realized / capital * 100.0, 3),
            "realizedR": round(realized / initial_risk_amount, 3),
            "fees": round(fees, 2),
            "exitReason": reason,
            "openedAt": int(position["openedAt"]),
            "closedAt": now,
            "durationSeconds": max(0, (now - int(position["openedAt"])) // 1000),
            "isWin": realized > 0,
        }
        paper_db.save_closed_trade(trade)
        paper_db.delete_position(str(position["id"]))
        self.positions_by_symbol.pop(symbol, None)
        self.last_position_persist_ms.pop(symbol, None)
        return trade

    def close_position_manually(self, position_id: str) -> Optional[Dict[str, Any]]:
        position = next((item for item in self.positions_by_symbol.values() if str(item.get("id")) == position_id), None)
        if not position:
            return None
        symbol = str(position["symbol"])
        state = self.market_data_service.symbol_states.get(symbol)
        if not state or float(state.current_price) <= 0:
            return None
        return self._close_position(symbol, float(state.current_price), "MANUAL")

    async def on_tick(self, symbol: str, price: float) -> None:
        position = self.positions_by_symbol.get(symbol)
        if not position:
            return
        settings = self.get_settings()
        side = str(position["side"])
        entry = float(position["entryPrice"])
        quantity = float(position.get("quantity", 0.0))
        initial_risk = max(float(position.get("initialRisk", abs(entry - float(position["stopLoss"])))), 1e-12)
        favorable_move = price - entry if side == "BUY" else entry - price
        r_multiple = favorable_move / initial_risk

        if r_multiple >= float(settings["breakevenAtR"]):
            fee_buffer = entry * float(settings["feeRatePct"]) / 100.0 * 2.0
            break_even = entry + fee_buffer if side == "BUY" else entry - fee_buffer
            if side == "BUY" and break_even > float(position["stopLoss"]):
                position["stopLoss"] = _round_price(break_even)
                position["breakEvenActivated"] = True
            elif side == "SELL" and break_even < float(position["stopLoss"]):
                position["stopLoss"] = _round_price(break_even)
                position["breakEvenActivated"] = True

        if r_multiple >= float(settings["trailingStartR"]):
            trail_distance = max(initial_risk * float(settings["trailingDistanceR"]), initial_risk * 0.5)
            trailing_stop = price - trail_distance if side == "BUY" else price + trail_distance
            if side == "BUY" and trailing_stop > float(position["stopLoss"]):
                position["stopLoss"] = _round_price(trailing_stop)
                position["trailingActivated"] = True
            elif side == "SELL" and trailing_stop < float(position["stopLoss"]):
                position["stopLoss"] = _round_price(trailing_stop)
                position["trailingActivated"] = True

        stop = float(position["stopLoss"])
        target = float(position["target1"])
        if (side == "BUY" and price <= stop) or (side == "SELL" and price >= stop):
            exit_reason = "TRAILING_STOP" if position.get("trailingActivated") else "BREAK_EVEN" if position.get("breakEvenActivated") else "STOP_LOSS"
            self._close_position(symbol, price, exit_reason)
            return
        if (side == "BUY" and price >= target) or (side == "SELL" and price <= target):
            self._close_position(symbol, price, "TARGET")
            return
        if _now_ms() - int(position["openedAt"]) >= int(float(settings["maxHoldMinutes"]) * 60_000):
            self._close_position(symbol, price, "TIME_EXIT")
            return

        gross = (price - entry) * quantity if side == "BUY" else (entry - price) * quantity
        fee_rate = float(settings["feeRatePct"]) / 100.0
        estimated_fees = (entry * quantity + price * quantity) * fee_rate
        unrealized = gross - estimated_fees
        capital = max(float(settings["capital"]), 1e-12)
        position["currentPrice"] = _round_price(price)
        position["unrealizedPnL"] = round(unrealized, 2)
        position["unrealizedPnLPercent"] = round(unrealized / capital * 100.0, 3)
        position["rMultiple"] = round(r_multiple, 2)
        position["lastUpdated"] = _now_ms()

        last_persist = self.last_position_persist_ms.get(symbol, 0)
        if _now_ms() - last_persist >= 750:
            paper_db.upsert_position(position)
            self.last_position_persist_ms[symbol] = _now_ms()
