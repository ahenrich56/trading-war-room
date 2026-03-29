"""
ICT Session / Killzone Engine.

Provides time-based session awareness for gold and futures trading.
Gold is heavily session-driven — London killzone is the primary session
for directional moves, NY AM for trend continuation, and Asian session
builds the range that London breaks.

All times are in ET (Eastern Time) to match CME futures sessions.
"""

from datetime import datetime, timezone, timedelta


# ET offset from UTC (handles EST/EDT approximately)
def _utc_to_et(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to approximate ET (EST = UTC-5, EDT = UTC-4)."""
    # Simple DST check: EDT is March second Sunday to November first Sunday
    year = utc_dt.year
    # March: second Sunday
    mar1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    mar_second_sun = mar1 + timedelta(days=(6 - mar1.weekday()) % 7 + 7)
    # November: first Sunday
    nov1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    nov_first_sun = nov1 + timedelta(days=(6 - nov1.weekday()) % 7)

    if mar_second_sun <= utc_dt.replace(tzinfo=timezone.utc) < nov_first_sun:
        return utc_dt - timedelta(hours=4)  # EDT
    return utc_dt - timedelta(hours=5)  # EST


# ═══════════════════════════════════════════════════════════
#  SESSION DEFINITIONS (ET hours)
# ═══════════════════════════════════════════════════════════

SESSIONS = {
    "ASIAN": {
        "start": 19,   # 7 PM ET
        "end": 0,       # 12 AM ET (midnight)
        "label": "Asian Session",
        "description": "Range-building session. Mark high/low for London breakout.",
        "confidence_modifier": 0.85,  # Reduce confidence — low directional conviction
        "crosses_midnight": True,
    },
    "ASIAN_LATE": {
        "start": 0,     # 12 AM ET
        "end": 2,       # 2 AM ET
        "label": "Late Asian / Pre-London",
        "description": "Transition period. Liquidity building for London open.",
        "confidence_modifier": 0.90,
        "crosses_midnight": False,
    },
    "LONDON_KILLZONE": {
        "start": 2,     # 2 AM ET
        "end": 5,       # 5 AM ET
        "label": "London Killzone",
        "description": "PRIMARY gold session. Highest probability for directional moves. ICT optimal trade entry window.",
        "confidence_modifier": 1.20,  # Boost confidence — prime trading window
        "crosses_midnight": False,
    },
    "LONDON_SESSION": {
        "start": 5,     # 5 AM ET
        "end": 8,       # 8 AM ET
        "label": "London Session",
        "description": "Continuation of London move. Watch for pullback entries.",
        "confidence_modifier": 1.10,
        "crosses_midnight": False,
    },
    "NY_KILLZONE": {
        "start": 8,     # 8 AM ET
        "end": 11,      # 11 AM ET
        "label": "NY AM Killzone",
        "description": "Highest volatility window. Trend continuation or reversal. Key news releases (NFP, CPI, FOMC).",
        "confidence_modifier": 1.15,
        "crosses_midnight": False,
    },
    "NY_LUNCH": {
        "start": 11,    # 11 AM ET
        "end": 13,      # 1 PM ET
        "label": "NY Lunch / Dead Zone",
        "description": "Low liquidity. Choppy price action. Avoid new entries.",
        "confidence_modifier": 0.70,  # Significant penalty
        "crosses_midnight": False,
    },
    "NY_PM": {
        "start": 13,    # 1 PM ET
        "end": 15,      # 3 PM ET
        "label": "NY PM Session",
        "description": "Afternoon session. Some institutional flows. FOMC announcements (Wed 2 PM ET).",
        "confidence_modifier": 0.95,
        "crosses_midnight": False,
    },
    "NY_CLOSE": {
        "start": 15,    # 3 PM ET
        "end": 17,      # 5 PM ET
        "label": "NY Close / Power Hour",
        "description": "End-of-day positioning. Can see sharp moves near close. Gold futures daily close at 5 PM ET.",
        "confidence_modifier": 0.80,  # Risky — thin liquidity into close
        "crosses_midnight": False,
    },
    "DEAD_ZONE": {
        "start": 17,    # 5 PM ET
        "end": 19,      # 7 PM ET
        "label": "Dead Zone",
        "description": "Between daily close and Asian open. Minimal liquidity. Avoid trading.",
        "confidence_modifier": 0.60,  # Heavy penalty
        "crosses_midnight": False,
    },
}


def get_current_session(utc_now: datetime = None) -> dict:
    """
    Determine the current ICT trading session based on UTC time.

    Returns:
        dict with keys: session_id, label, description, confidence_modifier,
        is_killzone, hour_et, day_of_week
    """
    if utc_now is None:
        utc_now = datetime.utcnow()

    et_now = _utc_to_et(utc_now)
    hour = et_now.hour
    day = et_now.strftime("%A")

    # Weekend check
    if day in ("Saturday", "Sunday"):
        return {
            "session_id": "WEEKEND",
            "label": "Weekend (Markets Closed)",
            "description": "Futures markets closed. No trading.",
            "confidence_modifier": 0.0,
            "is_killzone": False,
            "hour_et": hour,
            "day_of_week": day,
            "is_weekend": True,
        }

    # Find matching session
    for session_id, cfg in SESSIONS.items():
        if cfg.get("crosses_midnight"):
            # Handle sessions that cross midnight (e.g., 19-0)
            if hour >= cfg["start"] or hour < cfg["end"]:
                return _build_session_result(session_id, cfg, hour, day)
        else:
            if cfg["start"] <= hour < cfg["end"]:
                return _build_session_result(session_id, cfg, hour, day)

    # Fallback (shouldn't happen with full coverage)
    return {
        "session_id": "UNKNOWN",
        "label": "Unknown Session",
        "description": "Could not determine current session.",
        "confidence_modifier": 0.85,
        "is_killzone": False,
        "hour_et": hour,
        "day_of_week": day,
        "is_weekend": False,
    }


def _build_session_result(session_id: str, cfg: dict, hour: int, day: str) -> dict:
    is_killzone = session_id in ("LONDON_KILLZONE", "NY_KILLZONE")
    return {
        "session_id": session_id,
        "label": cfg["label"],
        "description": cfg["description"],
        "confidence_modifier": cfg["confidence_modifier"],
        "is_killzone": is_killzone,
        "hour_et": hour,
        "day_of_week": day,
        "is_weekend": False,
    }


# ═══════════════════════════════════════════════════════════
#  ASIAN RANGE DETECTION
# ═══════════════════════════════════════════════════════════

def compute_asian_range(df, utc_now: datetime = None) -> dict:
    """
    Compute the Asian session high/low from OHLCV dataframe.
    These levels act as key support/resistance for London breakout.

    Args:
        df: pandas DataFrame with DatetimeIndex and High/Low columns
        utc_now: current UTC time (for determining which Asian session to use)

    Returns:
        dict with asian_high, asian_low, asian_range, or empty if not available
    """
    if df is None or df.empty:
        return {}

    if utc_now is None:
        utc_now = datetime.utcnow()

    try:
        # Asian session: 7 PM - 12 AM ET = 0:00 - 5:00 UTC (EST) or 23:00 - 4:00 UTC (EDT)
        # Simplified: filter bars from roughly 23:00-05:00 UTC for today's Asian session
        et_now = _utc_to_et(utc_now)

        # If we're in Asian session or later, use today's Asian bars
        # Asian session ET: 19:00-00:00 = UTC 00:00-05:00 (next day)
        # We want bars from the most recent Asian session

        # Convert Asian session hours to UTC
        asian_start_utc = utc_now.replace(hour=23, minute=0, second=0, microsecond=0) - timedelta(days=1)
        asian_end_utc = utc_now.replace(hour=5, minute=0, second=0, microsecond=0)

        # If current time is before 5 UTC, the Asian session started yesterday at 23 UTC
        if utc_now.hour < 5:
            asian_start_utc = utc_now.replace(hour=23, minute=0, second=0, microsecond=0) - timedelta(days=1)
            asian_end_utc = utc_now.replace(hour=5, minute=0, second=0, microsecond=0)
        elif utc_now.hour >= 23:
            # Asian session just started
            asian_start_utc = utc_now.replace(hour=23, minute=0, second=0, microsecond=0)
            asian_end_utc = (utc_now + timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)
        else:
            # Past Asian session — use last night's
            asian_start_utc = (utc_now - timedelta(days=1)).replace(hour=23, minute=0, second=0, microsecond=0)
            asian_end_utc = utc_now.replace(hour=5, minute=0, second=0, microsecond=0)

        # Filter dataframe for Asian range bars
        mask = (df.index >= asian_start_utc) & (df.index <= asian_end_utc)
        asian_bars = df.loc[mask]

        if asian_bars.empty or len(asian_bars) < 2:
            return {}

        asian_high = float(asian_bars["High"].max())
        asian_low = float(asian_bars["Low"].min())
        asian_range = asian_high - asian_low

        return {
            "asian_high": round(asian_high, 2),
            "asian_low": round(asian_low, 2),
            "asian_range": round(asian_range, 2),
            "asian_mid": round((asian_high + asian_low) / 2, 2),
            "bars_count": len(asian_bars),
        }

    except Exception:
        return {}


# ═══════════════════════════════════════════════════════════
#  FORMAT FOR AI PROMPTS
# ═══════════════════════════════════════════════════════════

def format_session_for_ai(session: dict, asian_range: dict = None) -> str:
    """Format session context as text for AI agent prompts."""
    lines = ["═══ SESSION / KILLZONE CONTEXT ═══"]
    lines.append(f"  Current Session: {session['label']}")
    lines.append(f"  Time (ET): {session['hour_et']}:00 {session['day_of_week']}")
    lines.append(f"  Description: {session['description']}")

    if session.get("is_killzone"):
        lines.append("  ⚡ ACTIVE KILLZONE — High-probability trading window")
    elif session.get("confidence_modifier", 1.0) < 0.80:
        lines.append("  ⚠️ LOW-PROBABILITY SESSION — Consider avoiding new entries")

    modifier = session.get("confidence_modifier", 1.0)
    if modifier > 1.0:
        lines.append(f"  Confidence Boost: +{int((modifier - 1) * 100)}%")
    elif modifier < 1.0:
        lines.append(f"  Confidence Penalty: -{int((1 - modifier) * 100)}%")

    if asian_range:
        lines.append(f"\n  Asian Range: {asian_range['asian_low']} - {asian_range['asian_high']} (range: {asian_range['asian_range']})")
        lines.append(f"  Asian Mid: {asian_range['asian_mid']}")
        lines.append("  → Watch for London breakout above/below Asian range")

    return "\n".join(lines)
