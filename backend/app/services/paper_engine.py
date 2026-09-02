"""Compatibility shim for the retired paper engine module.

The only active strategy implementation is CryptoAlgoEngine in
app.services.crypto_algo_engine. Keep this alias temporarily so old imports fail
safe without maintaining a second strategy implementation.
"""

from app.services.crypto_algo_engine import CryptoAlgoEngine, DEFAULT_TRADING_SETTINGS

PaperTradingEngine = CryptoAlgoEngine

__all__ = ["PaperTradingEngine", "DEFAULT_TRADING_SETTINGS"]
