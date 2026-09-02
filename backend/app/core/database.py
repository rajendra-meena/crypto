import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings


class PaperTradingDatabase:
    """Small SQLite-backed persistence layer for paper trading state."""

    def __init__(self) -> None:
        settings = get_settings()
        db_path = Path(settings.database_path)
        if not db_path.is_absolute():
            db_path = Path.cwd() / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS paper_positions (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    signal_id TEXT,
                    payload TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol
                ON paper_positions(symbol);

                CREATE TABLE IF NOT EXISTS paper_closed_trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    closed_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_paper_closed_trades_closed_at
                ON paper_closed_trades(closed_at DESC);

                CREATE TABLE IF NOT EXISTS executed_signals (
                    signal_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    executed_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                """
            )
            conn.commit()

    def list_positions(self) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM paper_positions ORDER BY created_at ASC"
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def upsert_position(self, position: Dict[str, Any]) -> None:
        position_id = str(position["id"])
        symbol = str(position["symbol"])
        signal_id = position.get("signalId")
        created_at = int(position.get("openedAt") or 0)
        updated_at = int(position.get("lastUpdated") or created_at)
        payload = json.dumps(position, separators=(",", ":"))

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_positions(id, symbol, signal_id, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol=excluded.symbol,
                    signal_id=excluded.signal_id,
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (position_id, symbol, signal_id, payload, created_at, updated_at),
            )
            conn.commit()

    def delete_position(self, position_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM paper_positions WHERE id = ?", (position_id,))
            conn.commit()

    def list_closed_trades(self, limit: int = 500) -> List[Dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM paper_closed_trades ORDER BY closed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def save_closed_trade(self, trade: Dict[str, Any]) -> None:
        trade_id = str(trade["id"])
        symbol = str(trade["symbol"])
        closed_at = int(trade.get("closedAt") or 0)
        payload = json.dumps(trade, separators=(",", ":"))

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO paper_closed_trades(id, symbol, payload, closed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    symbol=excluded.symbol,
                    payload=excluded.payload,
                    closed_at=excluded.closed_at
                """,
                (trade_id, symbol, payload, closed_at),
            )
            conn.commit()

    def list_executed_signal_ids(self, limit: int = 2000) -> List[str]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT signal_id FROM executed_signals ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [str(row["signal_id"]) for row in rows]

    def mark_signal_executed(self, signal_id: str, symbol: str, executed_at: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO executed_signals(signal_id, symbol, executed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(signal_id) DO UPDATE SET
                    symbol=excluded.symbol,
                    executed_at=excluded.executed_at
                """,
                (signal_id, symbol, executed_at),
            )
            conn.commit()

    def get_engine_running(self) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_state WHERE key = 'engine_running'"
            ).fetchone()
        if not row:
            return False
        return str(row["value"]).lower() == "true"

    def set_engine_running(self, running: bool, updated_at: int) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_state(key, value, updated_at)
                VALUES ('engine_running', ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                ("true" if running else "false", updated_at),
            )
            conn.commit()


paper_db = PaperTradingDatabase()
