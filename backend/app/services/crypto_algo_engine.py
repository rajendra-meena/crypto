"""Compatibility alias for the retired crypto_algo_engine module.

The only active strategy implementation is CryptoStrategyEngine in
app.services.strategy_engine.
"""

from app.services.strategy_engine import CryptoStrategyEngine, DEFAULT_TRADING_SETTINGS

CryptoAlgoEngine = CryptoStrategyEngine

__all__ = ["CryptoAlgoEngine", "DEFAULT_TRADING_SETTINGS"]
