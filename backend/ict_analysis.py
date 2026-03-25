"""
ICT / Smart Money Concepts detection (CHoCH, BOS, Order Blocks, FVG).
Extracted from main.py for modularity.

Phase 5: Order blocks and FVGs are now cross-validated with order flow
data (volume, delta) to filter weak zones from strong institutional ones.
"""

import pandas as pd


def _detect_swing_points(high: pd.Series, low: pd.Series, lookback: int = 5) -> dict:
    """Detect swing highs and swing lows for structural analysis."""
    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(high) - lookback):
        # Swing High: highest point within lookback window
        if high.iloc[i] == high.iloc[i - lookback:i + lookback + 1].max():
            swing_highs.append({"index": i, "price": round(float(high.iloc[i]), 2)})
        # Swing Low: lowest point within lookback window
        if low.iloc[i] == low.iloc[i - lookback:i + lookback + 1].min():
            swing_lows.append({"index": i, "price": round(float(low.iloc[i]), 2)})

    return {"swing_highs": swing_highs[-8:], "swing_lows": swing_lows[-8:]}


def _detect_structure(high: pd.Series, low: pd.Series, lookback: int = 5) -> list:
    """Detect Break of Structure (BOS) and Change of Character (CHoCH)."""
    swings = _detect_swing_points(high, low, lookback)
    events = []

    # Track structure: Higher Highs/Higher Lows = uptrend, Lower Highs/Lower Lows = downtrend
    shs = swings["swing_highs"]
    sls = swings["swing_lows"]

    # Detect BOS / CHoCH from recent swing points
    if len(shs) >= 2 and len(sls) >= 2:
        last_sh = shs[-1]["price"]
        prev_sh = shs[-2]["price"]
        last_sl = sls[-1]["price"]
        prev_sl = sls[-2]["price"]

        # BOS: continuation of structure
        if last_sh > prev_sh and last_sl > prev_sl:
            events.append({"type": "BOS", "direction": "BULLISH", "level": last_sh, "detail": f"Higher High at {last_sh}, Higher Low at {last_sl}"})
        elif last_sh < prev_sh and last_sl < prev_sl:
            events.append({"type": "BOS", "direction": "BEARISH", "level": last_sl, "detail": f"Lower Low at {last_sl}, Lower High at {last_sh}"})

        # CHoCH: reversal of structure
        if last_sh > prev_sh and last_sl < prev_sl:
            events.append({"type": "CHoCH", "direction": "BULLISH", "level": last_sh, "detail": f"Broke previous high {prev_sh} → reversal up"})
        elif last_sh < prev_sh and last_sl > prev_sl:
            events.append({"type": "CHoCH", "direction": "BEARISH", "level": last_sl, "detail": f"Broke previous low {prev_sl} → reversal down"})

    return events


def _detect_order_blocks(df: pd.DataFrame, lookback: int = 20) -> list:
    """Detect bullish and bearish order blocks (last candle before a strong move)."""
    obs = []
    close = df["Close"]
    openp = df["Open"]
    high = df["High"]
    low = df["Low"]

    for i in range(max(1, len(df) - lookback), len(df) - 1):
        body = abs(float(close.iloc[i + 1]) - float(openp.iloc[i + 1]))
        avg_body = abs(close - openp).rolling(10).mean()
        if len(avg_body) > i and not pd.isna(avg_body.iloc[i]):
            threshold = float(avg_body.iloc[i]) * 2

            # Bullish OB: bearish candle followed by strong bullish candle
            if float(close.iloc[i]) < float(openp.iloc[i]) and body > threshold and float(close.iloc[i + 1]) > float(openp.iloc[i + 1]):
                obs.append({
                    "type": "BULLISH_OB",
                    "top": round(float(openp.iloc[i]), 2),
                    "bottom": round(float(close.iloc[i]), 2),
                    "index": i,
                })

            # Bearish OB: bullish candle followed by strong bearish candle
            if float(close.iloc[i]) > float(openp.iloc[i]) and body > threshold and float(close.iloc[i + 1]) < float(openp.iloc[i + 1]):
                obs.append({
                    "type": "BEARISH_OB",
                    "top": round(float(close.iloc[i]), 2),
                    "bottom": round(float(openp.iloc[i]), 2),
                    "index": i,
                })

    return obs[-4:]  # Return last 4 order blocks


def _detect_fvg(df: pd.DataFrame, lookback: int = 20) -> list:
    """Detect Fair Value Gaps (3-candle imbalances)."""
    fvgs = []
    high = df["High"]
    low = df["Low"]

    for i in range(max(2, len(df) - lookback), len(df)):
        h1 = float(high.iloc[i - 2])
        l3 = float(low.iloc[i])
        h3 = float(high.iloc[i])
        l1 = float(low.iloc[i - 2])

        # Bullish FVG: gap between candle 1 high and candle 3 low
        if l3 > h1:
            fvgs.append({
                "type": "BULLISH_FVG",
                "top": round(l3, 2),
                "bottom": round(h1, 2),
                "size": round(l3 - h1, 2),
            })

        # Bearish FVG: gap between candle 3 high and candle 1 low
        if h3 < l1:
            fvgs.append({
                "type": "BEARISH_FVG",
                "top": round(l1, 2),
                "bottom": round(h3, 2),
                "size": round(l1 - h3, 2),
            })

    return fvgs[-4:]  # Return last 4 FVGs


def _validate_order_blocks_with_flow(order_blocks: list, df: pd.DataFrame, delta_df: pd.DataFrame) -> list:
    """
    Cross-validate order blocks with volume/delta data.

    A strong OB has:
    - Volume > 2x average at formation
    - Delta matches direction (bullish OB = positive delta, bearish OB = negative delta)
    """
    if delta_df is None or delta_df.empty:
        for ob in order_blocks:
            ob["strength"] = "UNVALIDATED"
        return order_blocks

    avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1]) if len(df) >= 20 else float(df["Volume"].mean())

    for ob in order_blocks:
        idx = ob.get("index", 0)
        if idx >= len(delta_df):
            ob["strength"] = "UNVALIDATED"
            continue

        vol = float(delta_df["Volume"].iloc[idx])
        delta = float(delta_df["delta"].iloc[idx])
        vol_ratio = round(vol / avg_vol, 1) if avg_vol > 0 else 1.0

        ob["volume_ratio"] = vol_ratio
        ob["delta"] = round(delta, 0)

        direction_match = (
            (ob["type"] == "BULLISH_OB" and delta > 0) or
            (ob["type"] == "BEARISH_OB" and delta < 0)
        )

        if vol_ratio >= 2.0 and direction_match:
            ob["strength"] = "STRONG"
        elif vol_ratio >= 1.5 or direction_match:
            ob["strength"] = "MODERATE"
        else:
            ob["strength"] = "WEAK"

    return order_blocks


def _validate_fvgs_with_flow(fvgs: list, df: pd.DataFrame, delta_df: pd.DataFrame) -> list:
    """
    Cross-validate FVGs with delta data.

    A strong FVG has a large delta imbalance during the gap formation candle (middle of 3).
    """
    if delta_df is None or delta_df.empty:
        for fvg in fvgs:
            fvg["strength"] = "UNVALIDATED"
        return fvgs

    avg_vol = float(df["Volume"].rolling(20).mean().iloc[-1]) if len(df) >= 20 else float(df["Volume"].mean())

    for fvg in fvgs:
        # FVGs don't store index, but we can check the most recent delta bars
        # Mark based on overall recent delta direction matching FVG type
        recent_delta = float(delta_df["delta"].tail(5).sum())
        recent_vol = float(delta_df["Volume"].tail(3).mean())
        vol_ratio = round(recent_vol / avg_vol, 1) if avg_vol > 0 else 1.0

        direction_match = (
            (fvg["type"] == "BULLISH_FVG" and recent_delta > 0) or
            (fvg["type"] == "BEARISH_FVG" and recent_delta < 0)
        )

        fvg["volume_ratio"] = vol_ratio

        if vol_ratio >= 1.5 and direction_match:
            fvg["strength"] = "STRONG"
        elif direction_match:
            fvg["strength"] = "MODERATE"
        else:
            fvg["strength"] = "WEAK"

    return fvgs


def detect_ict_concepts(df: pd.DataFrame, order_flow_df: pd.DataFrame = None) -> dict:
    """
    Run all ICT/SMC detection algorithms on OHLCV data.

    If order_flow_df (with delta columns from compute_delta_series) is provided,
    order blocks and FVGs are cross-validated with volume/delta for strength grading.
    """
    if df.empty or len(df) < 20:
        return {"error": "Insufficient data for ICT analysis"}

    try:
        high = df["High"]
        low = df["Low"]

        swings = _detect_swing_points(high, low)
        structure = _detect_structure(high, low)
        order_blocks = _detect_order_blocks(df)
        fvgs = _detect_fvg(df)

        # Cross-validate with order flow if available
        if order_flow_df is not None and not order_flow_df.empty:
            order_blocks = _validate_order_blocks_with_flow(order_blocks, df, order_flow_df)
            fvgs = _validate_fvgs_with_flow(fvgs, df, order_flow_df)

        # Determine current market structure
        if structure:
            last_event = structure[-1]
            market_structure = f"{last_event['direction']} {last_event['type']}"
        else:
            market_structure = "RANGING"

        return {
            "market_structure": market_structure,
            "structure_events": structure,
            "order_blocks": order_blocks,
            "fair_value_gaps": fvgs,
            "recent_swing_highs": swings["swing_highs"][-3:],
            "recent_swing_lows": swings["swing_lows"][-3:],
        }
    except Exception as e:
        return {"error": str(e)}


def format_ict_for_ai(ict_data: dict) -> str:
    """Format ICT concepts into AI-readable text."""
    if "error" in ict_data:
        return f"ICT Analysis: {ict_data['error']}"

    lines = ["═══ ICT / SMART MONEY CONCEPTS ═══"]
    lines.append(f"  Market Structure: {ict_data.get('market_structure', 'Unknown')}")

    for evt in ict_data.get("structure_events", []):
        lines.append(f"  {evt['type']}: {evt['direction']} — {evt['detail']}")

    for ob in ict_data.get("order_blocks", []):
        strength = ob.get("strength", "")
        strength_tag = f" [{strength}]" if strength else ""
        vol_info = f" vol={ob['volume_ratio']}x" if "volume_ratio" in ob else ""
        lines.append(f"  {ob['type']}: Zone {ob['bottom']}-{ob['top']}{strength_tag}{vol_info}")

    for fvg in ict_data.get("fair_value_gaps", []):
        strength = fvg.get("strength", "")
        strength_tag = f" [{strength}]" if strength else ""
        lines.append(f"  {fvg['type']}: Gap {fvg['bottom']}-{fvg['top']} (size: {fvg['size']}){strength_tag}")

    shs = ict_data.get("recent_swing_highs", [])
    sls = ict_data.get("recent_swing_lows", [])
    if shs:
        lines.append(f"  Key Resistance (Swing Highs): {', '.join(str(s['price']) for s in shs)}")
    if sls:
        lines.append(f"  Key Support (Swing Lows): {', '.join(str(s['price']) for s in sls)}")

    return "\n".join(lines)
