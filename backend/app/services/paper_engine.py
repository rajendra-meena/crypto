"""Compatibility alias for the retired paper_engine module.

All paper strategy logic now lives in app.services.strategy_engine.
"""

from app.services.strategy_engine import CryptoStrategyEngine, DEFAULT_TRADING_SETTINGS

PaperTradingEngine = CryptoStrategyEngine

__all__ = ["PaperTradingEngine", "DEFAULT_TRADING_SETTINGS"]
