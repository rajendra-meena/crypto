import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import paper_db


DEFAULT_TRADING_SETTINGS: Dict[str, Any] = {
    "capital": 10000.0,
    "riskPerTradePct": 0.75,
    "maxDailyLossPct": 2.5,
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
    "breakEvenAtR": 1.0,
    "trailStartR": 1.5,
    "trailAtrMultiplier": 1.0,
    "maxTradeMinutes": 240,
    "minAtrPct": 0.03,
    "maxAtrPct": 2.50,
    "minVolumeRatio": 1.10,
    "btcTrendFilter": True,
    "feeRatePct": 0.05,
    "slippagePct": 0.02,
}


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
    output = [values[0]]
    for value in values[1:]:
        output.append(value * alpha + output[-1] * (1.0 - alpha))
    return output


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
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(candles: List[Any], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    start = max(1, len(candles) - period)
    true_ranges: List[float] = []
    for idx in range(start, len(candles)):
        candle = candles[idx]
        previous = candles[idx - 1]
        true_ranges.append(
            max(
                float(candle.high) - float(candle.low),
                abs(float(candle.high) - float(previous.close)),
                abs(float(candle.low) - float(previous.close)),
            )
        )
    return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0


def _round_price(value: float) -> float:
    if value < 10:
        return round(value, 6)
    if value < 100:
        return round(value, 4)
    return round(value, 2)


class PaperTradingEngine:
    """Backend-authoritative multi-timeframe crypto PAPER trading engine.

    Market data may be live, but this class never sends real exchange orders.
    All strategy decisions, risk checks, paper entries and exits live here so the
    browser cannot create or alter a trade.
    """

    STRATEGY_VERSION = "MTPA-3TF-v1"

    def __init__(self, market_data_service: Any):
        self.market_data_service = market_data_service
        self.latest_analysis: Dict[str, Dict[str, Any]] = {}
        self.latest_signals: Dict[str, Dict[str, Any]] = {}
        self.last_evaluated_trigger: Dict[str, int] = {}
        self.positions_by_symbol: Dict[str, Dict[str, Any]] = {
            str(position.get("symbol")): position for position in paper_db.list_positions()
        }
        self.last_position_persist_ms: Dict[str, int] = {}
        self.last_scan_ms = 0

    def get_settings(self) -> Dict[str, Any]:
        settings = dict(DEFAULT_TRADING_SETTINGS)
        settings.update(paper_db.get_trading_settings())
        return settings

    def get_analysis(self) -> List[Dict[str, Any]]:
        return [self.latest_analysis[key] for key in sorted(self.latest_analysis.keys())]

    def get_signals(self) -> List[Dict[str, Any]]:
        values = list(self.latest_signals.values())
        values.sort(key=lambda item: int(item.get("generatedAt", 0)), reverse=True)
        return values[:20]

    def get_risk_summary(self) -> Dict[str, Any]:
        settings = self.get_settings()
        today = paper_db.list_closed_trades_since(_today_start_ms())
        realized = sum(float(item.get("realizedPnL", 0.0)) for item in today)
        consecutive_losses = 0
        for trade in today:
            if float(trade.get("realizedPnL", 0.0)) < 0:
                consecutive_losses += 1
            else:
                break
        daily_limit = float(settings["capital"]) * float(settings["maxDailyLossPct"]) / 100.0
        return {
            "todayTrades": len(today),
            "todayRealizedPnL": round(realized, 2),
            "dailyLossLimit": round(daily_limit, 2),
            "dailyLossRemaining": round(max(0.0, daily_limit + realized), 2),
            "consecutiveLosses": consecutive_losses,
            "openPositions": len(self.positions_by_symbol),
            "engineRunning": paper_db.get_engine_running(),
        }

    def build_state(self) -> Dict[str, Any]:
        return {
            "version": self.STRATEGY_VERSION,
            "mode": "PAPER_ONLY",
            "engine_running": paper_db.get_engine_running(),
            "scanner": {
                "status": "ACTIVE",
                "lastScan": self.last_scan_ms,
                "symbols": sorted(self.market_data_service.symbol_states.keys()),
            },
            "positions": list(self.positions_by_symbol.values()),
            "closed_trades": paper_db.list_closed_trades(),
            "executed_signal_ids": paper_db.list_executed_signal_ids(),
            "signals": self.get_signals(),
            "analysis": self.get_analysis(),
            "risk": self.get_risk_summary(),
            "settings": self.get_settings(),
        }

    def _completed(self, symbol: str, timeframe: str, limit: int) -> List[Any]:
        state = self.market_data_service.symbol_states.get(symbol)
        if not state:
            return []
        candles = [
            candle
            for candle in state.get_candles(timeframe, limit + 10)
            if bool(getattr(candle, "is_complete", False))
        ]
        deduped: Dict[int, Any] = {int(candle.timestamp): candle for candle in candles}
        return [deduped[key] for key in sorted(deduped.keys())][-limit:]

    def _htf_direction(self, symbol: str) -> str:
        candles = self._completed(symbol, "15m", 60)
        if len(candles) < 55:
            return "NEUTRAL"
        closes = [float(candle.close) for candle in candles]
        ema20 = _ema_series(closes, 20)
        ema50 = _ema_series(closes, 50)
        if len(ema20) < 6 or len(ema50) < 1:
            return "NEUTRAL"
        slope = ema20[-1] - ema20[-6]
        close = closes[-1]
        if close > ema20[-1] > ema50[-1] and slope > 0:
            return "BULLISH"
        if close < ema20[-1] < ema50[-1] and slope < 0:
            return "BEARISH"
        return "NEUTRAL"

    def analyze_symbol(self, symbol: str) -> Dict[str, Any]:
        candles15 = self._completed(symbol, "15m", 60)
        candles5 = self._completed(symbol, "5m", 50)
        candles1 = self._completed(symbol, "1m", 40)
        now = _now_ms()

        base = {
            "symbol": symbol,
            "strategyVersion": self.STRATEGY_VERSION,
            "status": "INSUFFICIENT_DATA",
            "side": "WAIT",
            "setupScore": 0,
            "evaluatedAt": now,
            "triggerCandleTime": 0,
            "reason": "Waiting for enough completed 15m, 5m and 1m candles",
            "blockers": ["INSUFFICIENT_DATA"],
            "htfTrend": "NEUTRAL",
            "mtfTrend": "NEUTRAL",
            "breakout1m": False,
            "rsi5m": 50.0,
            "atr5m": 0.0,
            "atrPct": 0.0,
            "volumeRatio": 0.0,
            "bodyQuality": 0.0,
            "support": 0.0,
            "resistance": 0.0,
        }

        if len(candles15) < 55 or len(candles5) < 30 or len(candles1) < 25:
            return base

        close15 = [float(c.close) for c in candles15]
        ema20_15 = _ema_series(close15, 20)
        ema50_15 = _ema_series(close15, 50)
        htf_slope = ema20_15[-1] - ema20_15[-6]
        htf = "NEUTRAL"
        if close15[-1] > ema20_15[-1] > ema50_15[-1] and htf_slope > 0:
            htf = "BULLISH"
        elif close15[-1] < ema20_15[-1] < ema50_15[-1] and htf_slope < 0:
            htf = "BEARISH"

        close5 = [float(c.close) for c in candles5]
        ema9_5 = _ema_series(close5, 9)
        ema21_5 = _ema_series(close5, 21)
        mtf = "NEUTRAL"
        if close5[-1] > ema9_5[-1] > ema21_5[-1]:
            mtf = "BULLISH"
        elif close5[-1] < ema9_5[-1] < ema21_5[-1]:
            mtf = "BEARISH"

        rsi5 = _rsi(close5, 14)
        atr5 = _atr(candles5, 14)
        price5 = max(close5[-1], 1e-12)
        atr_pct = atr5 / price5 * 100.0

        trigger = candles1[-1]
        prior1 = candles1[-7:-1]
        prior_high = max(float(c.high) for c in prior1)
        prior_low = min(float(c.low) for c in prior1)
        bullish_breakout = float(trigger.close) > prior_high
        bearish_breakout = float(trigger.close) < prior_low

        previous_volumes = [float(c.volume or 0.0) for c in candles1[-21:-1]]
        average_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else 0.0
        volume_ratio = float(trigger.volume or 0.0) / average_volume if average_volume > 0 else 0.0

        candle_range = max(float(trigger.high) - float(trigger.low), 1e-12)
        body = abs(float(trigger.close) - float(trigger.open))
        body_quality = body / candle_range
        bullish_body = float(trigger.close) > float(trigger.open)
        bearish_body = float(trigger.close) < float(trigger.open)

        support = min(float(c.low) for c in candles5[-10:])
        resistance = max(float(c.high) for c in candles5[-10:])

        direction = "WAIT"
        if htf == "BULLISH" and mtf == "BULLISH":
            direction = "BUY"
        elif htf == "BEARISH" and mtf == "BEARISH":
            direction = "SELL"

        score = 0
        reasons: List[str] = []
        blockers: List[str] = []

        if direction != "WAIT":
            score += 20
            reasons.append("15m regime aligned")
            score += 15
            reasons.append("5m EMA trend aligned")
        else:
            blockers.append("TIMEFRAME_TREND_NOT_ALIGNED")

        breakout_ok = bullish_breakout if direction == "BUY" else bearish_breakout if direction == "SELL" else False
        if breakout_ok:
            score += 25
            reasons.append("1m completed-candle breakout")
        else:
            blockers.append("NO_COMPLETED_1M_BREAKOUT")

        rsi_ok = (52.0 <= rsi5 <= 72.0) if direction == "BUY" else (28.0 <= rsi5 <= 48.0) if direction == "SELL" else False
        if rsi_ok:
            score += 10
            reasons.append("5m RSI confirms momentum")
        elif direction != "WAIT":
            blockers.append("RSI_NOT_CONFIRMING")

        settings = self.get_settings()
        volume_ok = volume_ratio >= float(settings["minVolumeRatio"])
        if volume_ok:
            score += 10
            reasons.append("volume expansion")
        else:
            blockers.append("LOW_TRIGGER_VOLUME")

        volatility_ok = float(settings["minAtrPct"]) <= atr_pct <= float(settings["maxAtrPct"])
        if volatility_ok:
            score += 10
            reasons.append("tradable volatility")
        else:
            blockers.append("VOLATILITY_OUT_OF_RANGE")

        body_ok = body_quality >= 0.55 and ((direction == "BUY" and bullish_body) or (direction == "SELL" and bearish_body))
        if body_ok:
            score += 10
            reasons.append("strong trigger candle")
        else:
            blockers.append("WEAK_TRIGGER_CANDLE")

        overextended = False
        if atr5 > 0:
            distance_from_ema = abs(close5[-1] - ema21_5[-1]) / atr5
            overextended = distance_from_ema > 2.5
            if overextended:
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
        has_hard_blocker = any(item in hard_blockers for item in blockers)
        setup_ready = direction != "WAIT" and score >= int(settings["minSetupScore"]) and not has_hard_blocker

        status = "READY" if setup_ready else "WATCHING"
        reason = " · ".join(reasons) if reasons else "Waiting for multi-timeframe alignment"
        if blockers:
            reason += " | " + ", ".join(blockers)

        return {
            **base,
            "status": status,
            "side": direction,
            "setupScore": min(100, score),
            "triggerCandleTime": int(trigger.timestamp),
            "reason": reason,
            "blockers": blockers,
            "htfTrend": htf,
            "mtfTrend": mtf,
            "breakout1m": breakout_ok,
            "rsi5m": round(rsi5, 1),
            "atr5m": _round_price(atr5),
            "atrPct": round(atr_pct, 3),
            "volumeRatio": round(volume_ratio, 2),
            "bodyQuality": round(body_quality, 2),
            "support": _round_price(support),
            "resistance": _round_price(resistance),
        }

    def _risk_block_reason(self, symbol: str, side: str, settings: Dict[str, Any]) -> Optional[str]:
        if symbol in self.positions_by_symbol:
            return "POSITION_ALREADY_OPEN"
        if len(self.positions_by_symbol) >= int(settings["maxConcurrentTrades"]):
            return "MAX_CONCURRENT_TRADES"

        same_direction = sum(1 for p in self.positions_by_symbol.values() if str(p.get("side")) == side)
        if same_direction >= int(settings["maxSameDirection"]):
            return "MAX_SAME_DIRECTION_EXPOSURE"

        today = paper_db.list_closed_trades_since(_today_start_ms())
        if len(today) >= int(settings["maxTradesPerDay"]):
            return "MAX_TRADES_PER_DAY"

        realized = sum(float(item.get("realizedPnL", 0.0)) for item in today)
        max_daily_loss = float(settings["capital"]) * float(settings["maxDailyLossPct"]) / 100.0
        if realized <= -max_daily_loss:
            paper_db.set_engine_running(False, _now_ms())
            return "MAX_DAILY_LOSS"

        consecutive_losses = 0
        for trade in today:
            if float(trade.get("realizedPnL", 0.0)) < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= int(settings["maxConsecutiveLosses"]):
            paper_db.set_engine_running(False, _now_ms())
            return "MAX_CONSECUTIVE_LOSSES"

        last_closed = paper_db.get_last_closed_trade(symbol)
        cooldown_ms = int(float(settings["cooldownMinutes"]) * 60_000)
        if last_closed and _now_ms() - int(last_closed.get("closedAt", 0)) < cooldown_ms:
            return "COOLDOWN"
        return None

    def _create_signal(self, analysis: Dict[str, Any], status: str, reason_suffix: Optional[str] = None) -> Dict[str, Any]:
        settings = self.get_settings()
        symbol = str(analysis["symbol"])
        side = str(analysis["side"])
        state = self.market_data_service.symbol_states.get(symbol)
        raw_price = float(state.current_price) if state else 0.0

        atr_distance = float(analysis["atr5m"]) * float(settings["atrStopMultiplier"])
        min_distance = raw_price * float(settings["minStopPct"]) / 100.0
        structure_distance = (raw_price - float(analysis["support"])) if side == "BUY" else (float(analysis["resistance"]) - raw_price)
        stop_distance = max(atr_distance, min_distance, structure_distance if structure_distance > 0 else 0.0)
        max_distance = raw_price * float(settings["maxStopPct"]) / 100.0

        slippage = float(settings["slippagePct"]) / 100.0
        entry = raw_price * (1.0 + slippage if side == "BUY" else 1.0 - slippage)
        stop = entry - stop_distance if side == "BUY" else entry + stop_distance
        target = entry + stop_distance * float(settings["targetRR"]) if side == "BUY" else entry - stop_distance * float(settings["targetRR"])
        signal_id = f"{self.STRATEGY_VERSION}-{symbol}-{analysis['triggerCandleTime']}-{side}"

        final_status = status
        suffix = reason_suffix
        if stop_distance > max_distance > 0:
            final_status = "FILTERED"
            suffix = "STOP_TOO_WIDE"

        reason = str(analysis["reason"])
        if suffix:
            reason += f" | {suffix}"

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
        self.latest_analysis[symbol] = analysis

        trigger_time = int(analysis.get("triggerCandleTime", 0))
        if trigger_time <= 0:
            self.latest_signals.pop(symbol, None)
            return

        if self.last_evaluated_trigger.get(symbol) == trigger_time:
            return
        self.last_evaluated_trigger[symbol] = trigger_time

        if analysis["status"] != "READY" or analysis["side"] == "WAIT":
            self.latest_signals.pop(symbol, None)
            return

        settings = self.get_settings()
        if not paper_db.get_engine_running():
            self.latest_signals[symbol] = self._create_signal(analysis, "BLOCKED", "ENGINE_OFF")
            return

        state = self.market_data_service.symbol_states.get(symbol)
        if not state or float(state.current_price) <= 0:
            self.latest_signals[symbol] = self._create_signal(analysis, "BLOCKED", "NO_LIVE_PRICE")
            return

        block_reason = self._risk_block_reason(symbol, str(analysis["side"]), settings)
        signal = self._create_signal(analysis, "READY", block_reason)
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

        entry = float(signal["entry"])
        stop = float(signal["stopLoss"])
        initial_risk = abs(entry - stop)
        if initial_risk <= 0:
            signal["status"] = "FILTERED"
            signal["reason"] += " | INVALID_STOP_DISTANCE"
            self.latest_signals[symbol] = signal
            return

        risk_amount = float(settings["capital"]) * float(settings["riskPerTradePct"]) / 100.0
        quantity = risk_amount / initial_risk
        notional = quantity * entry
        max_notional = float(settings["capital"]) * float(settings["maxLeverage"])
        if notional > max_notional:
            notional = max_notional
            quantity = notional / max(entry, 1e-12)

        now = _now_ms()
        position = {
            "id": f"POS-{symbol}-{now}",
            "signalId": signal_id,
            "strategyVersion": self.STRATEGY_VERSION,
            "symbol": symbol,
            "side": analysis["side"],
            "entryPrice": entry,
            "currentPrice": float(state.current_price),
            "stopLoss": stop,
            "initialStopLoss": stop,
            "target1": float(signal["target1"]),
            "target2": float(signal["target2"]),
            "initialRisk": _round_price(initial_risk),
            "atrAtEntry": float(analysis["atr5m"]),
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

    def _close_position(self, symbol: str, raw_price: float, exit_reason: str) -> Optional[Dict[str, Any]]:
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
        now = _now_ms()
        capital = max(float(settings["capital"]), 1e-12)
        initial_risk_cash = max(float(position.get("initialRisk", abs(entry - float(position["stopLoss"])))) * quantity, 1e-12)
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
            "realizedR": round(realized / initial_risk_cash, 3),
            "fees": round(fees, 2),
            "exitReason": exit_reason,
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

    def close_position_by_id(self, position_id: str) -> Optional[Dict[str, Any]]:
        position = next((p for p in self.positions_by_symbol.values() if str(p.get("id")) == position_id), None)
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

        # Break-even is only activated after a full 1R favorable move.
        if r_multiple >= float(settings["breakEvenAtR"]):
            fee_buffer = entry * float(settings["feeRatePct"]) / 100.0 * 2.0
            break_even_stop = entry + fee_buffer if side == "BUY" else entry - fee_buffer
            if side == "BUY" and break_even_stop > float(position["stopLoss"]):
                position["stopLoss"] = _round_price(break_even_stop)
                position["breakEvenActivated"] = True
            elif side == "SELL" and break_even_stop < float(position["stopLoss"]):
                position["stopLoss"] = _round_price(break_even_stop)
                position["breakEvenActivated"] = True

        # After 1.5R, trail by the entry-time 5m ATR; never loosen the stop.
        if r_multiple >= float(settings["trailStartR"]):
            trail_distance = max(
                float(position.get("atrAtEntry", initial_risk)) * float(settings["trailAtrMultiplier"]),
                initial_risk * 0.50,
            )
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
            reason = "TRAILING_STOP" if position.get("trailingActivated") else "BREAK_EVEN" if position.get("breakEvenActivated") else "STOP_LOSS"
            self._close_position(symbol, price, reason)
            return
        if (side == "BUY" and price >= target) or (side == "SELL" and price <= target):
            self._close_position(symbol, price, "TARGET")
            return

        max_duration_ms = int(float(settings["maxTradeMinutes"]) * 60_000)
        if _now_ms() - int(position["openedAt"]) >= max_duration_ms:
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

        # Persist at a controlled cadence; stop/target checks above still happen on every tick.
        last_persist = self.last_position_persist_ms.get(symbol, 0)
        if _now_ms() - last_persist >= 750:
            paper_db.upsert_position(position)
            self.last_position_persist_ms[symbol] = _now_ms()
