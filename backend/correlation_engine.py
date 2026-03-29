"""
Intermarket Correlation Engine.

Computes rolling correlations between gold and key intermarket drivers
(DXY, US10Y, VIX) and detects SMT (Smart Money Technique) divergences.

Key relationships for gold:
  - Gold / DXY:   Strong inverse (-0.40 to -0.60)
  - Gold / US10Y: Strong inverse (-0.60 to -0.80) — real yields drive gold
  - Gold / VIX:   Moderate positive (+0.20 to +0.40, spikes to +0.70 in crises)
"""

import pandas as pd
import numpy as np
import yfinance as yf


# ═══════════════════════════════════════════════════════════
#  DATA FETCHING
# ═══════════════════════════════════════════════════════════

def _fetch_intermarket_series(timeframe: str = "5m") -> dict:
    """
    Fetch close prices for gold and intermarket instruments.
    Returns dict of ticker -> pd.Series (close prices).
    """
    tf_map = {
        "1m": ("1m", "1d"),
        "5m": ("5m", "5d"),
        "15m": ("15m", "5d"),
        "1h": ("1h", "30d"),
    }
    interval, period = tf_map.get(timeframe, ("5m", "5d"))

    tickers = {
        "GOLD": "GC=F",
        "DXY": "DX-Y.NYB",
        "US10Y": "^TNX",
        "VIX": "^VIX",
    }

    series = {}
    for label, symbol in tickers.items():
        try:
            tk = yf.Ticker(symbol)
            df = tk.history(period=period, interval=interval)
            if not df.empty and len(df) >= 20:
                series[label] = df["Close"]
        except Exception:
            pass

    return series


# ═══════════════════════════════════════════════════════════
#  ROLLING CORRELATION
# ═══════════════════════════════════════════════════════════

def compute_correlations(series: dict, window: int = 20) -> dict:
    """
    Compute rolling correlations between gold and intermarket instruments.

    Returns dict with correlation values and interpretations.
    """
    gold = series.get("GOLD")
    if gold is None or len(gold) < window:
        return {}

    results = {}

    for label in ("DXY", "US10Y", "VIX"):
        other = series.get(label)
        if other is None or len(other) < window:
            continue

        # Align indices
        combined = pd.DataFrame({"gold": gold, label.lower(): other}).dropna()
        if len(combined) < window:
            continue

        # Rolling correlation
        rolling_corr = combined["gold"].rolling(window).corr(combined[label.lower()])
        current_corr = float(rolling_corr.iloc[-1]) if not pd.isna(rolling_corr.iloc[-1]) else 0.0

        # Interpretation
        if abs(current_corr) > 0.7:
            strength = "STRONG"
        elif abs(current_corr) > 0.4:
            strength = "MODERATE"
        elif abs(current_corr) > 0.2:
            strength = "WEAK"
        else:
            strength = "NEGLIGIBLE"

        direction = "POSITIVE" if current_corr > 0 else "NEGATIVE"

        results[label] = {
            "correlation": round(current_corr, 3),
            "strength": strength,
            "direction": direction,
            "window": window,
        }

    return results


# ═══════════════════════════════════════════════════════════
#  SMT DIVERGENCE DETECTION
# ═══════════════════════════════════════════════════════════

def detect_smt_divergences(series: dict, lookback: int = 20) -> list:
    """
    Detect Smart Money Technique (SMT) divergences between gold and DXY.

    SMT divergence: When gold makes a higher high but DXY fails to make
    a lower low (or vice versa). This signals institutional reversal.
    """
    gold = series.get("GOLD")
    dxy = series.get("DXY")

    if gold is None or dxy is None:
        return []
    if len(gold) < lookback or len(dxy) < lookback:
        return []

    combined = pd.DataFrame({"gold": gold, "dxy": dxy}).dropna()
    if len(combined) < lookback:
        return []

    divergences = []
    recent = combined.tail(lookback)

    gold_vals = recent["gold"].values
    dxy_vals = recent["dxy"].values

    # Find swing highs/lows in the lookback window
    # Use simple 3-bar swing detection
    for i in range(2, len(gold_vals) - 2):
        # Gold higher high + DXY NOT lower low = bearish SMT divergence
        if (gold_vals[i] > gold_vals[i - 2] and
                gold_vals[i] > gold_vals[i + 1] and  # gold swing high
                dxy_vals[i] > dxy_vals[i - 2]):  # DXY also higher (should be lower for normal inverse)
            divergences.append({
                "type": "BEARISH_SMT",
                "description": "Gold higher high but DXY NOT lower low — bearish reversal signal",
                "gold_price": round(float(gold_vals[i]), 2),
                "dxy_price": round(float(dxy_vals[i]), 3),
                "bars_ago": len(gold_vals) - 1 - i,
            })

        # Gold lower low + DXY NOT higher high = bullish SMT divergence
        if (gold_vals[i] < gold_vals[i - 2] and
                gold_vals[i] < gold_vals[i + 1] and  # gold swing low
                dxy_vals[i] < dxy_vals[i - 2]):  # DXY also lower (should be higher for normal inverse)
            divergences.append({
                "type": "BULLISH_SMT",
                "description": "Gold lower low but DXY NOT higher high — bullish reversal signal",
                "gold_price": round(float(gold_vals[i]), 2),
                "dxy_price": round(float(dxy_vals[i]), 3),
                "bars_ago": len(gold_vals) - 1 - i,
            })

    return divergences


# ═══════════════════════════════════════════════════════════
#  CONFIDENCE MODIFIER
# ═══════════════════════════════════════════════════════════

def compute_correlation_modifier(correlations: dict, smt_divergences: list, signal_direction: str) -> dict:
    """
    Compute a confidence modifier based on intermarket alignment.

    Args:
        correlations: dict from compute_correlations()
        smt_divergences: list from detect_smt_divergences()
        signal_direction: "LONG", "SHORT", or "NO_TRADE"

    Returns:
        dict with confidence_modifier (0.5-1.3), label, and reasons
    """
    if not correlations or signal_direction == "NO_TRADE":
        return {"confidence_modifier": 1.0, "label": "NEUTRAL", "reasons": []}

    modifier = 1.0
    reasons = []

    # DXY alignment check (strongest driver)
    dxy = correlations.get("DXY", {})
    if dxy:
        dxy_corr = dxy.get("correlation", 0)
        # Normal: Gold and DXY are inversely correlated
        # If going LONG gold, DXY should be falling (correlation stays negative)
        # If DXY is currently rising (positive recent trend), that's contra for LONG
        # We use the correlation value directly as a proxy

        if signal_direction == "LONG":
            if dxy_corr > 0.3:
                # Gold and DXY moving together = abnormal = risk
                modifier *= 0.85
                reasons.append(f"DXY positive correlation ({dxy_corr:.2f}) — headwind for LONG gold")
            elif dxy_corr < -0.5:
                # Strong inverse = normal = supportive
                modifier *= 1.10
                reasons.append(f"DXY strong inverse ({dxy_corr:.2f}) — supportive for LONG gold")
        elif signal_direction == "SHORT":
            if dxy_corr > 0.3:
                modifier *= 1.10
                reasons.append(f"DXY positive correlation ({dxy_corr:.2f}) — supports SHORT gold")
            elif dxy_corr < -0.5:
                modifier *= 0.85
                reasons.append(f"DXY strong inverse ({dxy_corr:.2f}) — headwind for SHORT gold")

    # VIX alignment check (fear gauge)
    vix = correlations.get("VIX", {})
    if vix:
        vix_corr = vix.get("correlation", 0)
        if signal_direction == "LONG" and vix_corr > 0.4:
            modifier *= 1.05
            reasons.append(f"VIX positive correlation ({vix_corr:.2f}) — safe-haven bid supports LONG")
        elif signal_direction == "SHORT" and vix_corr > 0.4:
            modifier *= 0.90
            reasons.append(f"VIX positive correlation ({vix_corr:.2f}) — safe-haven bid opposes SHORT")

    # US10Y alignment (yields inverse to gold)
    us10y = correlations.get("US10Y", {})
    if us10y:
        y_corr = us10y.get("correlation", 0)
        if signal_direction == "LONG" and y_corr > 0.3:
            modifier *= 0.90
            reasons.append(f"Yields positive correlation ({y_corr:.2f}) — rising yields headwind for LONG")
        elif signal_direction == "SHORT" and y_corr > 0.3:
            modifier *= 1.05
            reasons.append(f"Yields positive correlation ({y_corr:.2f}) — rising yields support SHORT")

    # SMT divergence override (strongest signal)
    recent_smt = [d for d in smt_divergences if d.get("bars_ago", 99) <= 5]
    for div in recent_smt[:1]:  # Only use most recent
        if div["type"] == "BEARISH_SMT" and signal_direction == "LONG":
            modifier *= 0.80
            reasons.append(f"BEARISH SMT divergence detected ({div['bars_ago']} bars ago) — contra for LONG")
        elif div["type"] == "BULLISH_SMT" and signal_direction == "SHORT":
            modifier *= 0.80
            reasons.append(f"BULLISH SMT divergence detected ({div['bars_ago']} bars ago) — contra for SHORT")
        elif div["type"] == "BULLISH_SMT" and signal_direction == "LONG":
            modifier *= 1.15
            reasons.append(f"BULLISH SMT divergence confirmed ({div['bars_ago']} bars ago) — supports LONG")
        elif div["type"] == "BEARISH_SMT" and signal_direction == "SHORT":
            modifier *= 1.15
            reasons.append(f"BEARISH SMT divergence confirmed ({div['bars_ago']} bars ago) — supports SHORT")

    # Clamp modifier
    modifier = max(0.50, min(1.30, round(modifier, 3)))

    # Label
    if modifier >= 1.10:
        label = "SUPPORTIVE"
    elif modifier <= 0.85:
        label = "HEADWIND"
    else:
        label = "NEUTRAL"

    return {
        "confidence_modifier": modifier,
        "label": label,
        "reasons": reasons,
    }


# ═══════════════════════════════════════════════════════════
#  FULL ANALYSIS (ENTRY POINT)
# ═══════════════════════════════════════════════════════════

def analyze_intermarket(timeframe: str = "5m", signal_direction: str = "NO_TRADE") -> dict:
    """
    Full intermarket analysis: fetch data, compute correlations, detect SMT, compute modifier.

    Args:
        timeframe: data timeframe
        signal_direction: preliminary signal direction from 5-factor scoring

    Returns:
        dict with correlations, smt_divergences, modifier, label, reasons
    """
    try:
        series = _fetch_intermarket_series(timeframe)
        if not series or "GOLD" not in series:
            return {
                "correlations": {},
                "smt_divergences": [],
                "confidence_modifier": 1.0,
                "label": "NO_DATA",
                "reasons": ["Intermarket data unavailable"],
            }

        correlations = compute_correlations(series)
        smt_divergences = detect_smt_divergences(series)
        modifier_result = compute_correlation_modifier(correlations, smt_divergences, signal_direction)

        return {
            "correlations": correlations,
            "smt_divergences": smt_divergences,
            **modifier_result,
        }

    except Exception as e:
        return {
            "correlations": {},
            "smt_divergences": [],
            "confidence_modifier": 1.0,
            "label": "ERROR",
            "reasons": [f"Intermarket analysis error: {str(e)}"],
        }


def format_correlation_for_ai(analysis: dict) -> str:
    """Format intermarket analysis as text for AI agent prompts."""
    lines = ["═══ INTERMARKET CORRELATION ANALYSIS ═══"]

    correlations = analysis.get("correlations", {})
    if not correlations:
        lines.append("  No intermarket data available")
        return "\n".join(lines)

    for label, data in correlations.items():
        corr = data["correlation"]
        strength = data["strength"]
        direction = data["direction"]
        lines.append(f"  Gold/{label}: {corr:+.3f} ({strength} {direction})")

    smt = analysis.get("smt_divergences", [])
    if smt:
        lines.append("\n  SMT Divergences:")
        for div in smt[-3:]:
            lines.append(f"    {div['type']}: {div['description']} ({div['bars_ago']} bars ago)")

    modifier = analysis.get("confidence_modifier", 1.0)
    label = analysis.get("label", "NEUTRAL")
    if modifier != 1.0:
        lines.append(f"\n  Intermarket Verdict: {label} ({modifier}x modifier)")

    reasons = analysis.get("reasons", [])
    for r in reasons:
        lines.append(f"    → {r}")

    return "\n".join(lines)
