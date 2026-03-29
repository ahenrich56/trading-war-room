"""
CFTC Commitment of Traders (COT) Engine.

Fetches weekly COT data for gold futures from the CFTC and provides
institutional positioning context for signal generation.

COT reports show positions of:
  - Commercials (hedgers): Typically contrarian — extreme short = bullish for gold
  - Large Speculators (managed money): Trend followers — extreme long = crowded trade risk
  - Small Speculators: Retail — often wrong at extremes

Released weekly on Fridays at 3:30 PM ET, data as of Tuesday close.
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

# Try to import cot_reports, fall back gracefully
try:
    import cot_reports as cot
    COT_AVAILABLE = True
except ImportError:
    COT_AVAILABLE = False


# ═══════════════════════════════════════════════════════════
#  CACHE CONFIG
# ═══════════════════════════════════════════════════════════

CACHE_DIR = Path(__file__).parent / ".cot_cache"
CACHE_FILE = CACHE_DIR / "gold_cot.json"
CACHE_MAX_AGE_HOURS = 168  # 7 days — COT is weekly data

GOLD_CONTRACT_CODE = "088691"  # CFTC code for gold futures


def _is_cache_valid() -> bool:
    if not CACHE_FILE.exists():
        return False
    try:
        mtime = CACHE_FILE.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600
        return age_hours < CACHE_MAX_AGE_HOURS
    except Exception:
        return False


def _read_cache() -> dict:
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_cache(data: dict):
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
#  COT DATA FETCHING
# ═══════════════════════════════════════════════════════════

def fetch_gold_cot() -> dict:
    """
    Fetch latest COT data for gold futures.
    Uses cot_reports library to pull from CFTC.

    Returns dict with positioning data or empty dict on failure.
    """
    # Check cache first
    if _is_cache_valid():
        cached = _read_cache()
        if cached:
            return cached

    if not COT_AVAILABLE:
        return _get_fallback_data()

    try:
        # Fetch disaggregated futures report (most detailed)
        # cot_reports fetches from CFTC and returns a DataFrame
        year = datetime.utcnow().year
        df = cot.cot_year(year=year, cot_report_type="traders_in_financial_futures_futopt")

        if df is None or df.empty:
            # Try legacy report format
            df = cot.cot_year(year=year, cot_report_type="legacy_futopt")

        if df is None or df.empty:
            return _get_fallback_data()

        # Filter for gold
        gold_mask = df["CFTC Contract Market Code"].astype(str).str.contains(GOLD_CONTRACT_CODE)
        if not gold_mask.any():
            # Try name-based search
            gold_mask = df["Market and Exchange Names"].str.contains("GOLD", case=False, na=False)

        gold_df = df[gold_mask].sort_index(ascending=False)
        if gold_df.empty:
            return _get_fallback_data()

        # Get latest and previous week
        latest = gold_df.iloc[0]
        previous = gold_df.iloc[1] if len(gold_df) > 1 else None

        result = _parse_cot_row(latest, previous)
        _write_cache(result)
        return result

    except Exception as e:
        print(f"COT fetch error: {e}")
        return _get_fallback_data()


def _parse_cot_row(latest, previous=None) -> dict:
    """Parse a COT DataFrame row into structured data."""
    result = {
        "report_date": str(latest.name) if hasattr(latest, "name") else "unknown",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
    }

    # Try different column name patterns (varies by report type)
    col_patterns = {
        "commercial_long": [
            "Comm Positions-Long (All)",
            "Commercial Positions-Long (All)",
            "Dealer Positions-Long (All)",
        ],
        "commercial_short": [
            "Comm Positions-Short (All)",
            "Commercial Positions-Short (All)",
            "Dealer Positions-Short (All)",
        ],
        "large_spec_long": [
            "NonComm Positions-Long (All)",
            "Noncommercial Positions-Long (All)",
            "Asset Mgr Positions-Long (All)",
        ],
        "large_spec_short": [
            "NonComm Positions-Short (All)",
            "Noncommercial Positions-Short (All)",
            "Asset Mgr Positions-Short (All)",
        ],
        "small_spec_long": [
            "Nonrept Positions-Long (All)",
            "NonRept Positions-Long (All)",
        ],
        "small_spec_short": [
            "Nonrept Positions-Short (All)",
            "NonRept Positions-Short (All)",
        ],
        "open_interest": [
            "Open Interest (All)",
            "Open Interest",
        ],
    }

    positions = {}
    for key, patterns in col_patterns.items():
        for col in patterns:
            if col in latest.index:
                try:
                    positions[key] = int(float(latest[col]))
                except (ValueError, TypeError):
                    positions[key] = 0
                break
        if key not in positions:
            positions[key] = 0

    # Compute net positions
    commercial_net = positions.get("commercial_long", 0) - positions.get("commercial_short", 0)
    large_spec_net = positions.get("large_spec_long", 0) - positions.get("large_spec_short", 0)
    small_spec_net = positions.get("small_spec_long", 0) - positions.get("small_spec_short", 0)

    result["positions"] = {
        "commercial_long": positions.get("commercial_long", 0),
        "commercial_short": positions.get("commercial_short", 0),
        "commercial_net": commercial_net,
        "large_spec_long": positions.get("large_spec_long", 0),
        "large_spec_short": positions.get("large_spec_short", 0),
        "large_spec_net": large_spec_net,
        "small_spec_long": positions.get("small_spec_long", 0),
        "small_spec_short": positions.get("small_spec_short", 0),
        "small_spec_net": small_spec_net,
        "open_interest": positions.get("open_interest", 0),
    }

    # Week-over-week changes
    if previous is not None:
        try:
            prev_positions = {}
            for key, patterns in col_patterns.items():
                for col in patterns:
                    if col in previous.index:
                        try:
                            prev_positions[key] = int(float(previous[col]))
                        except (ValueError, TypeError):
                            prev_positions[key] = 0
                        break

            prev_comm_net = prev_positions.get("commercial_long", 0) - prev_positions.get("commercial_short", 0)
            prev_spec_net = prev_positions.get("large_spec_long", 0) - prev_positions.get("large_spec_short", 0)

            result["changes"] = {
                "commercial_net_change": commercial_net - prev_comm_net,
                "large_spec_net_change": large_spec_net - prev_spec_net,
            }
        except Exception:
            result["changes"] = {}
    else:
        result["changes"] = {}

    # Interpretation
    result["interpretation"] = _interpret_cot(result)

    return result


def _interpret_cot(data: dict) -> dict:
    """Interpret COT positioning for gold."""
    positions = data.get("positions", {})
    changes = data.get("changes", {})

    commercial_net = positions.get("commercial_net", 0)
    large_spec_net = positions.get("large_spec_net", 0)
    comm_change = changes.get("commercial_net_change", 0)
    spec_change = changes.get("large_spec_net_change", 0)

    signals = []
    bias = "NEUTRAL"

    # Commercials (contrarian indicator)
    if commercial_net < -200000:
        signals.append("Commercials EXTREMELY short — historically bullish for gold (contrarian)")
        bias = "BULLISH"
    elif commercial_net < -100000:
        signals.append("Commercials moderately short — slight bullish bias")
    elif commercial_net > 0:
        signals.append("Commercials net long — unusual, potentially bearish reversal")
        bias = "BEARISH"

    # Large Specs (crowding indicator)
    if large_spec_net > 250000:
        signals.append("Large speculators EXTREMELY long — crowded trade, reversal risk")
        if bias != "BEARISH":
            bias = "CAUTION_LONG"
    elif large_spec_net > 150000:
        signals.append("Large speculators heavily long — momentum but watch for unwind")
    elif large_spec_net < 50000:
        signals.append("Large speculators light positioning — room to add (bullish potential)")
        if bias == "NEUTRAL":
            bias = "BULLISH"

    # Week-over-week changes
    if comm_change > 20000:
        signals.append(f"Commercials added {comm_change:,} net long WoW — bullish shift")
    elif comm_change < -20000:
        signals.append(f"Commercials added {abs(comm_change):,} net short WoW — bearish shift")

    if spec_change > 20000:
        signals.append(f"Large specs added {spec_change:,} net long WoW — momentum building")
    elif spec_change < -20000:
        signals.append(f"Large specs reduced {abs(spec_change):,} net WoW — liquidation")

    return {
        "bias": bias,
        "signals": signals,
    }


def _get_fallback_data() -> dict:
    """Return empty structure when COT data is unavailable."""
    return {
        "report_date": "unavailable",
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "positions": {},
        "changes": {},
        "interpretation": {
            "bias": "NEUTRAL",
            "signals": ["COT data unavailable — install cot_reports: pip install cot_reports"],
        },
    }


# ═══════════════════════════════════════════════════════════
#  FORMAT FOR AI PROMPTS
# ═══════════════════════════════════════════════════════════

def format_cot_for_ai(cot_data: dict) -> str:
    """Format COT data as text for AI agent prompts."""
    lines = ["═══ CFTC COT REPORT (Institutional Positioning) ═══"]

    if not cot_data or cot_data.get("report_date") == "unavailable":
        lines.append("  COT data not available")
        return "\n".join(lines)

    lines.append(f"  Report Date: {cot_data.get('report_date', 'unknown')}")

    positions = cot_data.get("positions", {})
    if positions:
        lines.append(f"  Commercial Net: {positions.get('commercial_net', 0):,} contracts")
        lines.append(f"    (Long: {positions.get('commercial_long', 0):,} | Short: {positions.get('commercial_short', 0):,})")
        lines.append(f"  Large Spec Net: {positions.get('large_spec_net', 0):,} contracts")
        lines.append(f"    (Long: {positions.get('large_spec_long', 0):,} | Short: {positions.get('large_spec_short', 0):,})")
        lines.append(f"  Open Interest: {positions.get('open_interest', 0):,}")

    changes = cot_data.get("changes", {})
    if changes:
        comm_chg = changes.get("commercial_net_change", 0)
        spec_chg = changes.get("large_spec_net_change", 0)
        if comm_chg or spec_chg:
            lines.append(f"\n  Week-over-Week Changes:")
            lines.append(f"    Commercial Net Change: {comm_chg:+,}")
            lines.append(f"    Large Spec Net Change: {spec_chg:+,}")

    interp = cot_data.get("interpretation", {})
    if interp:
        lines.append(f"\n  COT Bias: {interp.get('bias', 'NEUTRAL')}")
        for s in interp.get("signals", []):
            lines.append(f"    → {s}")

    return "\n".join(lines)
