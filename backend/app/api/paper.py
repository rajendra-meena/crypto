"""Retired compatibility module.

Trading state and controls are served only from /api/trading/* via
app.api.trading. This module intentionally exposes no routes so there is a
single authoritative API surface.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/paper", tags=["retired-paper-api"])
market_data_service = None
paper_engine = None
