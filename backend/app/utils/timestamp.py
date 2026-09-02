"""
Timestamp normalization utilities for Delta Exchange.

Delta Exchange India WebSocket sends timestamps in nanoseconds since epoch.
REST API returns timestamps in seconds.

This module provides deterministic timestamp normalization with validation.
"""

import time
from datetime import datetime, timezone
from typing import Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class TimestampUnit(Enum):
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


@dataclass
class NormalizedTimestamp:
    """Result of timestamp normalization."""
    timestamp_ms: int
    unit_detected: TimestampUnit
    utc_datetime: datetime
    age_seconds: float
    is_future: bool
    is_reasonable: bool
    warnings: list[str]


def detect_timestamp_unit(timestamp: int) -> TimestampUnit:
    """
    Detect the unit of a timestamp based on its magnitude.
    
    Thresholds (as of year 2024):
    - Seconds: ~1.7e9 (10 digits)
    - Milliseconds: ~1.7e12 (13 digits)
    - Microseconds: ~1.7e15 (16 digits)
    - Nanoseconds: ~1.7e18 (19 digits)
    """
    if timestamp < 1e11:  # < 100 billion seconds (before year 1973)
        return TimestampUnit.SECONDS
    elif timestamp < 1e14:  # < 100 trillion milliseconds (before year 5000)
        return TimestampUnit.MILLISECONDS
    elif timestamp < 1e17:  # < 100 quadrillion microseconds
        return TimestampUnit.MICROSECONDS
    else:
        return TimestampUnit.NANOSECONDS


def normalize_timestamp(timestamp: Optional[int], source: str = "unknown") -> NormalizedTimestamp:
    """
    Normalize a timestamp to milliseconds since epoch (UTC).
    
    Args:
        timestamp: Raw timestamp value (can be seconds, ms, us, or ns)
        source: Description of source for logging (e.g., "delta_ws", "delta_rest")
    
    Returns:
        NormalizedTimestamp with validated and converted timestamp
    
    Raises:
        ValueError: If timestamp is None or invalid
    """
    if timestamp is None:
        raise ValueError(f"Timestamp is None from {source}")
    
    if timestamp < 0:
        raise ValueError(f"Negative timestamp from {source}: {timestamp}")
    
    now_ms = int(time.time() * 1000)
    now_sec = now_ms / 1000
    
    unit = detect_timestamp_unit(timestamp)
    
    # Convert to milliseconds
    if unit == TimestampUnit.SECONDS:
        ts_ms = timestamp * 1000
    elif unit == TimestampUnit.MILLISECONDS:
        ts_ms = timestamp
    elif unit == TimestampUnit.MICROSECONDS:
        ts_ms = timestamp // 1000
    elif unit == TimestampUnit.NANOSECONDS:
        ts_ms = timestamp // 1_000_000
    else:
        raise ValueError(f"Unknown timestamp unit for {timestamp}")
    
    # Calculate age
    age_seconds = (now_ms - ts_ms) / 1000
    
    # Check if timestamp is in the future (with 1 second tolerance for clock skew)
    is_future = ts_ms > now_ms + 1000
    
    # Check if timestamp is reasonable (not too old, not too far in future)
    # Reasonable: within 30 days in past, 1 minute in future
    is_reasonable = age_seconds <= 30 * 24 * 3600 and ts_ms <= now_ms + 60_000
    
    warnings = []
    if is_future:
        warnings.append(f"Timestamp from {source} is in the future by {(ts_ms - now_ms)/1000:.1f}s")
    if age_seconds > 3600:
        warnings.append(f"Timestamp from {source} is {age_seconds/3600:.1f} hours old")
    if age_seconds > 86400:
        warnings.append(f"Timestamp from {source} is {age_seconds/86400:.1f} days old (likely replay/historical data)")
    
    utc_dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    
    return NormalizedTimestamp(
        timestamp_ms=ts_ms,
        unit_detected=unit,
        utc_datetime=utc_dt,
        age_seconds=age_seconds,
        is_future=is_future,
        is_reasonable=is_reasonable,
        warnings=warnings,
    )


def format_timestamp_log(normalized: NormalizedTimestamp, source: str, price: float, symbol: str) -> str:
    """Format a detailed log entry for a timestamp."""
    return (
        f"[{source}] {symbol} price={price:.6f} | "
        f"raw_ts={normalized.timestamp_ms}ms | "
        f"unit={normalized.unit_detected.value} | "
        f"utc={normalized.utc_datetime.isoformat()} | "
        f"age={normalized.age_seconds:.2f}s | "
        f"future={normalized.is_future} | "
        f"reasonable={normalized.is_reasonable} | "
        f"warnings={normalized.warnings}"
    )


# Deterministic test cases
TEST_CASES = [
    # (input_timestamp, expected_unit, expected_ms, description)
    (1704067200, TimestampUnit.SECONDS, 1704067200_000, "seconds (2024-01-01)"),
    (1704067200_000, TimestampUnit.MILLISECONDS, 1704067200_000, "milliseconds (2024-01-01)"),
    (1704067200_000_000, TimestampUnit.MICROSECONDS, 1704067200_000, "microseconds (2024-01-01)"),
    (1704067200_000_000_000, TimestampUnit.NANOSECONDS, 1704067200_000, "nanoseconds (2024-01-01)"),
    # Edge cases near boundaries
    (9999999999, TimestampUnit.SECONDS, 9999999999000, "seconds near boundary"),
    (10000000000000, TimestampUnit.MILLISECONDS, 10000000000000, "milliseconds near boundary"),
    (10000000000000000, TimestampUnit.MICROSECONDS, 10000000000000, "microseconds near boundary"),
    (10000000000000000000, TimestampUnit.NANOSECONDS, 10000000000000, "nanoseconds near boundary"),
]


def run_timestamp_tests() -> bool:
    """Run deterministic timestamp normalization tests."""
    all_passed = True
    
    print("Running timestamp normalization tests...")
    for timestamp, expected_unit, expected_ms, description in TEST_CASES:
        try:
            result = normalize_timestamp(timestamp, "test")
            
            # Check unit detection
            if result.unit_detected != expected_unit:
                print(f"FAIL [{description}]: unit mismatch. got={result.unit_detected.value}, expected={expected_unit.value}")
                all_passed = False
                continue
            
            # Check conversion
            if result.timestamp_ms != expected_ms:
                print(f"FAIL [{description}]: ms mismatch. got={result.timestamp_ms}, expected={expected_ms}")
                all_passed = False
                continue
            
            print(f"PASS [{description}]: {result.unit_detected.value} -> {result.timestamp_ms}ms (UTC: {result.utc_datetime.isoformat()})")
            
        except Exception as e:
            print(f"FAIL [{description}]: exception={e}")
            all_passed = False
    
    if all_passed:
        print("\n[OK] All timestamp tests PASSED")
    else:
        print("\n[FAIL] Some timestamp tests FAILED")
    
    return all_passed


if __name__ == "__main__":
    run_timestamp_tests()