"""
Enhanced Signal Scoring Engine.

Replaces the simplistic calculate_strategy_score with a 5-factor confluence
model that adapts to market regime, grades signals (A+/A/B/C/F), and uses
order flow as a final gate to filter false signals.

Factors:
  1. TREND     — EMA alignment, price vs VWAP, EMA 50/200 position
  2. MOMENTUM  — RSI, MACD histogram, Stochastic RSI
  3. STRUCTURE  — BOS/CHoCH, order block proximity, FVG alignment
  4. ORDER_FLOW — Delta bias, CVD trend, divergences, absorption
  5. VOLUME     — Volume ratio, stacked imbalances
"""


# ═══════════════════════════════════════════════════════════
#  MARKET REGIME DETECTION
# ═══════════════════════════════════════════════════════════

def detect_market_regime(adx, atr_pct, volume_ratio, cvd_trend, rsi):
    """
    Classify current market into a regime for dynamic weight adjustment.

    Returns one of: TRENDING_UP, TRENDING_DOWN, RANGING, HIGH_VOLATILITY, LOW_LIQUIDITY
    """
    if adx is None:
        adx = 20
    if atr_pct is None:
        atr_pct = 0.5
    if volume_ratio is None:
        volume_ratio = 1.0
    if rsi is None:
        rsi = 50

    # High volatility override
    if atr_pct > 1.5 and volume_ratio > 2.0:
        return "HIGH_VOLATILITY"

    # Low liquidity
    if volume_ratio < 0.4:
        return "LOW_LIQUIDITY"

    # Trending
    if adx > 25:
        if rsi > 55 and cvd_trend in ("RISING", "FLAT"):
            return "TRENDING_UP"
        elif rsi < 45 and cvd_trend in ("FALLING", "FLAT"):
            return "TRENDING_DOWN"
        # Strong ADX but mixed signals — still trending in the direction of momentum
        if rsi > 50:
            return "TRENDING_UP"
        return "TRENDING_DOWN"

    # Ranging
    return "RANGING"


# ═══════════════════════════════════════════════════════════
#  DYNAMIC WEIGHT PROFILES
# ═══════════════════════════════════════════════════════════

REGIME_WEIGHTS = {
    "TRENDING_UP": {
        "trend": 30, "momentum": 25, "structure": 15, "order_flow": 20, "volume": 10,
    },
    "TRENDING_DOWN": {
        "trend": 30, "momentum": 25, "structure": 15, "order_flow": 20, "volume": 10,
    },
    "RANGING": {
        "trend": 10, "momentum": 30, "structure": 25, "order_flow": 20, "volume": 15,
    },
    "HIGH_VOLATILITY": {
        "trend": 15, "momentum": 20, "structure": 15, "order_flow": 30, "volume": 20,
    },
    "LOW_LIQUIDITY": {
        "trend": 20, "momentum": 25, "structure": 20, "order_flow": 15, "volume": 20,
    },
}


# ═══════════════════════════════════════════════════════════
#  FACTOR SCORING FUNCTIONS
# ═══════════════════════════════════════════════════════════

def _score_trend(ema9, ema21, ema50, ema200, current_price, vwap):
    """Score trend factor: -100 to +100."""
    score = 0
    signals = []

    # EMA 9/21 cross (primary short-term trend)
    if ema9 is not None and ema21 is not None:
        if ema9 > ema21:
            score += 30
            signals.append("EMA9 > EMA21 (bullish cross)")
        else:
            score -= 30
            signals.append("EMA9 < EMA21 (bearish cross)")

    # EMA 50/200 alignment (macro trend)
    if ema50 is not None and ema200 is not None:
        if ema50 > ema200:
            score += 20
            signals.append("EMA50 > EMA200 (golden cross)")
        else:
            score -= 20
            signals.append("EMA50 < EMA200 (death cross)")

    # Price vs VWAP
    if current_price is not None and vwap is not None and vwap > 0:
        if current_price > vwap:
            score += 15
            signals.append("Price above VWAP")
        else:
            score -= 15
            signals.append("Price below VWAP")

    # EMA alignment quality (all EMAs stacked in order)
    if all(v is not None for v in [ema9, ema21, ema50, ema200]):
        if ema9 > ema21 > ema50 > ema200:
            score += 35
            signals.append("Perfect bullish EMA stack")
        elif ema9 < ema21 < ema50 < ema200:
            score -= 35
            signals.append("Perfect bearish EMA stack")

    return max(-100, min(100, score)), signals


def _score_momentum(rsi, macd_hist, stoch_k, stoch_d):
    """Score momentum factor: -100 to +100."""
    score = 0
    signals = []

    # RSI
    if rsi is not None:
        if rsi > 70:
            score -= 25
            signals.append(f"RSI overbought ({rsi:.1f})")
        elif rsi < 30:
            score += 25
            signals.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 60:
            score += 15
            signals.append(f"RSI bullish ({rsi:.1f})")
        elif rsi < 40:
            score -= 15
            signals.append(f"RSI bearish ({rsi:.1f})")

    # MACD histogram
    if macd_hist is not None:
        if macd_hist > 0:
            score += 25
            signals.append(f"MACD histogram positive ({macd_hist:.2f})")
        else:
            score -= 25
            signals.append(f"MACD histogram negative ({macd_hist:.2f})")

    # Stochastic RSI
    if stoch_k is not None and stoch_d is not None:
        if stoch_k > 80 and stoch_d > 80:
            score -= 20
            signals.append(f"StochRSI overbought (K={stoch_k:.1f})")
        elif stoch_k < 20 and stoch_d < 20:
            score += 20
            signals.append(f"StochRSI oversold (K={stoch_k:.1f})")
        elif stoch_k > stoch_d:
            score += 10
            signals.append("StochRSI K > D (bullish)")
        else:
            score -= 10
            signals.append("StochRSI K < D (bearish)")

    return max(-100, min(100, score)), signals


def _score_structure(ict_data, current_price):
    """Score market structure factor from ICT data: -100 to +100."""
    score = 0
    signals = []

    if not ict_data or not current_price:
        return 0, ["No ICT data available"]

    # BOS / CHoCH direction
    structure_events = ict_data.get("structure_events", [])
    if structure_events:
        recent = structure_events[-1]
        stype = recent.get("type", "")
        sdir = recent.get("direction", "")
        label = f"{sdir} {stype}" if sdir else stype
        if "bullish" in sdir.lower() or "bullish" in stype.lower():
            score += 30
            signals.append(f"Bullish {label}")
        elif "bearish" in sdir.lower() or "bearish" in stype.lower():
            score -= 30
            signals.append(f"Bearish {label}")

    # Order block proximity (ICT returns top/bottom, not high/low)
    order_blocks = ict_data.get("order_blocks", [])
    for ob in order_blocks[-3:]:
        ob_top = ob.get("top", 0)
        ob_bottom = ob.get("bottom", 0)
        ob_type = ob.get("type", "")

        if ob_bottom <= current_price <= ob_top:
            if "bullish" in ob_type.lower():
                score += 25
                signals.append(f"Price at bullish OB ({ob_bottom:.2f}-{ob_top:.2f})")
            elif "bearish" in ob_type.lower():
                score -= 25
                signals.append(f"Price at bearish OB ({ob_bottom:.2f}-{ob_top:.2f})")
            break

    # FVG alignment (ICT returns fair_value_gaps with top/bottom)
    fair_value_gaps = ict_data.get("fair_value_gaps", [])
    for fvg in fair_value_gaps[-3:]:
        fvg_top = fvg.get("top", 0)
        fvg_bottom = fvg.get("bottom", 0)
        fvg_type = fvg.get("type", "")

        if fvg_bottom <= current_price <= fvg_top:
            if "bullish" in fvg_type.lower():
                score += 15
                signals.append("Price filling bullish FVG")
            elif "bearish" in fvg_type.lower():
                score -= 15
                signals.append("Price filling bearish FVG")
            break

    # Liquidity grabs — strong reversal signals
    for grab in ict_data.get("liquidity_grabs", []):
        grab_type = grab.get("type", "")
        if "bullish" in grab_type.lower():
            score += 20
            signals.append(f"Bullish liquidity grab at {grab.get('level', '?')}")
        elif "bearish" in grab_type.lower():
            score -= 20
            signals.append(f"Bearish liquidity grab at {grab.get('level', '?')}")

    # Swing Failure Patterns — high-probability reversal
    for sfp in ict_data.get("swing_failure_patterns", []):
        sfp_type = sfp.get("type", "")
        if "bullish" in sfp_type.lower():
            score += 15
            signals.append(f"Bullish SFP at {sfp.get('level', '?')}")
        elif "bearish" in sfp_type.lower():
            score -= 15
            signals.append(f"Bearish SFP at {sfp.get('level', '?')}")

    # Judas swing — session open trap
    judas = ict_data.get("judas_swing")
    if judas:
        judas_type = judas.get("type", "")
        if "bullish" in judas_type.lower():
            score += 10
            signals.append("Bullish Judas swing detected")
        elif "bearish" in judas_type.lower():
            score -= 10
            signals.append("Bearish Judas swing detected")

    return max(-100, min(100, score)), signals


def _score_order_flow(order_flow_summary):
    """Score order flow factor: -100 to +100."""
    score = 0
    signals = []

    if not order_flow_summary:
        return 0, ["No order flow data"]

    summary = order_flow_summary.get("summary", {})

    # Delta bias
    bias = summary.get("overall_delta_bias", "NEUTRAL")
    if bias == "BULLISH":
        score += 30
        signals.append("Delta bias BULLISH (last 10 bars)")
    elif bias == "BEARISH":
        score -= 30
        signals.append("Delta bias BEARISH (last 10 bars)")

    # CVD trend
    cvd = summary.get("cvd_trend", "FLAT")
    if cvd == "RISING":
        score += 25
        signals.append("CVD trend RISING")
    elif cvd == "FALLING":
        score -= 25
        signals.append("CVD trend FALLING")

    # Divergences (strong contra-signals)
    divergences = order_flow_summary.get("divergences", [])
    for div in divergences[-2:]:
        if div.get("type") == "BEARISH_DIVERGENCE":
            score -= 35
            signals.append(f"BEARISH CVD divergence at {div.get('price_level', '?')}")
        elif div.get("type") == "BULLISH_DIVERGENCE":
            score += 35
            signals.append(f"BULLISH CVD divergence at {div.get('price_level', '?')}")

    # Absorption zones
    absorptions = order_flow_summary.get("absorptions", [])
    for abs_zone in absorptions[-2:]:
        if abs_zone.get("type") == "BULLISH_ABSORPTION":
            score += 15
            signals.append(f"Bullish absorption at {abs_zone.get('price', '?')}")
        elif abs_zone.get("type") == "BEARISH_ABSORPTION":
            score -= 15
            signals.append(f"Bearish absorption at {abs_zone.get('price', '?')}")

    # VWAP deviation (mean-reversion risk)
    vwap_dev = summary.get("vwap_deviation", 0)
    if abs(vwap_dev) > 2:
        # Extended — strong contra-signal for continued direction
        if vwap_dev > 2:
            score -= 30
            signals.append(f"Extended above VWAP ({vwap_dev}σ) — mean reversion risk")
        elif vwap_dev < -2:
            score += 30
            signals.append(f"Extended below VWAP ({vwap_dev}σ) — bounce potential")

    return max(-100, min(100, score)), signals


def _score_volume(volume_ratio, stacked_imbalances):
    """Score volume factor: -100 to +100."""
    score = 0
    signals = []

    # Volume ratio
    if volume_ratio is not None:
        if volume_ratio > 2.0:
            score += 30
            signals.append(f"High volume ({volume_ratio:.1f}x avg)")
        elif volume_ratio > 1.5:
            score += 15
            signals.append(f"Above-avg volume ({volume_ratio:.1f}x)")
        elif volume_ratio < 0.5:
            score -= 20
            signals.append(f"Low volume ({volume_ratio:.1f}x) — weak conviction")

    # Stacked imbalances
    if stacked_imbalances:
        for imb in stacked_imbalances[-2:]:
            direction = imb.get("direction", "")
            bars = imb.get("bars_count", 0)
            if direction == "BUY":
                score += 25
                signals.append(f"Stacked BUY imbalance ({bars} bars)")
            elif direction == "SELL":
                score -= 25
                signals.append(f"Stacked SELL imbalance ({bars} bars)")

    return max(-100, min(100, score)), signals


# ═══════════════════════════════════════════════════════════
#  CONFLUENCE EVALUATOR
# ═══════════════════════════════════════════════════════════

def _determine_direction(weighted_score):
    """Convert weighted score to direction with tighter thresholds."""
    if weighted_score > 20:
        return "LONG"
    elif weighted_score < -20:
        return "SHORT"
    return "NO_TRADE"


def _apply_hard_gates(adx, volume_ratio, atr, direction):
    """
    Hard gates that force NO_TRADE regardless of score.
    Returns (should_block: bool, reason: str).
    """
    if direction == "NO_TRADE":
        return False, ""

    if atr is None or atr == 0:
        return True, "ATR unavailable — cannot size stops"

    if adx is not None and adx < 18:
        return True, f"ADX={adx:.1f} < 18 — insufficient trend strength"

    if volume_ratio is not None and volume_ratio < 0.3:
        return True, f"Volume ratio={volume_ratio:.1f}x < 0.3 — insufficient liquidity"

    return False, ""


def _grade_signal(weighted_score, factors_aligned, order_flow_agrees, has_divergence):
    """
    Grade signal quality based on confluence.

    A+ : 4-5 factors aligned, score > 50, no contra-divergences
    A  : 3-4 factors aligned, score > 35
    B  : 2-3 factors, score > 20
    C  : Mixed signals or weak alignment
    F  : Order flow contradicts or too many opposing factors
    """
    abs_score = abs(weighted_score)

    if has_divergence and not order_flow_agrees:
        return "C"  # Mixed signals, not a total failure

    if factors_aligned >= 4 and abs_score > 55 and order_flow_agrees:
        return "A+"
    elif factors_aligned >= 3 and abs_score > 40 and order_flow_agrees:
        return "A"
    elif factors_aligned >= 2 and abs_score > 27:
        return "B"
    elif abs_score > 10:
        return "C"
    return "F"


def calculate_enhanced_score(
    indicators: dict,
    ict_data: dict = None,
    order_flow_data: dict = None,
    mtf_confluence: dict = None,
    session_data: dict = None,
    correlation_data: dict = None,
):
    """
    Enhanced multi-factor confluence scoring.

    Args:
        indicators: dict from compute_indicators() — RSI, EMA, MACD, ADX, etc.
        ict_data: dict from detect_ict_concepts() — BOS, CHoCH, OBs, FVGs
        order_flow_data: dict from compute_order_flow_summary() — delta, CVD, profile
        mtf_confluence: dict from compute_mtf_order_flow() — MTF multiplier

    Returns:
        dict with score, direction, signals, grade, regime, confluences, etc.
    """
    # Extract indicator values
    ema9 = indicators.get("EMA_9")
    ema21 = indicators.get("EMA_21")
    ema50 = indicators.get("EMA_50")
    ema200 = indicators.get("EMA_200")
    rsi = indicators.get("RSI_14")
    macd_hist = indicators.get("MACD_histogram")
    adx = indicators.get("ADX")
    volume_ratio = indicators.get("volume_ratio")
    current_price = indicators.get("current_price")
    vwap = indicators.get("VWAP")
    stoch_k = indicators.get("StochRSI_K")
    stoch_d = indicators.get("StochRSI_D")
    atr = indicators.get("ATR_14")

    # ATR as percentage for regime detection
    atr_pct = (atr / current_price * 100) if atr and current_price and current_price > 0 else 0.5

    # Order flow summary
    of_summary = order_flow_data or {}
    cvd_trend = of_summary.get("summary", {}).get("cvd_trend", "FLAT")
    stacked_imbalances = of_summary.get("stacked_imbalances", [])

    # 1. Detect regime
    regime = detect_market_regime(adx, atr_pct, volume_ratio, cvd_trend, rsi)
    weights = REGIME_WEIGHTS.get(regime, REGIME_WEIGHTS["RANGING"])

    # 2. Score each factor
    trend_score, trend_signals = _score_trend(ema9, ema21, ema50, ema200, current_price, vwap)
    momentum_score, momentum_signals = _score_momentum(rsi, macd_hist, stoch_k, stoch_d)
    structure_score, structure_signals = _score_structure(ict_data, current_price)
    of_score, of_signals = _score_order_flow(of_summary)
    vol_score, vol_signals = _score_volume(volume_ratio, stacked_imbalances)

    # 3. Weighted composite score
    weighted_score = (
        trend_score * weights["trend"] / 100 +
        momentum_score * weights["momentum"] / 100 +
        structure_score * weights["structure"] / 100 +
        of_score * weights["order_flow"] / 100 +
        vol_score * weights["volume"] / 100
    )
    # 3b. Apply MTF order flow confluence multiplier
    mtf_multiplier = 1.0
    mtf_label = "NEUTRAL"
    if mtf_confluence:
        mtf_multiplier = mtf_confluence.get("confluence_multiplier", 1.0)
        mtf_label = mtf_confluence.get("confluence_label", "NEUTRAL")

    weighted_score = weighted_score * mtf_multiplier

    # 3c. Apply session confidence modifier (killzones boost, dead zones penalize)
    session_modifier = 1.0
    session_label = "UNKNOWN"
    if session_data:
        session_modifier = session_data.get("confidence_modifier", 1.0)
        session_label = session_data.get("label", "UNKNOWN")
        # Don't apply session modifier to NO_TRADE direction (avoid amplifying noise)
        if abs(weighted_score) > 10:
            weighted_score = weighted_score * session_modifier

    # 3d. Apply intermarket correlation modifier
    correlation_modifier = 1.0
    correlation_label = "NEUTRAL"
    if correlation_data:
        correlation_modifier = correlation_data.get("confidence_modifier", 1.0)
        correlation_label = correlation_data.get("label", "NEUTRAL")
        if abs(weighted_score) > 10:
            weighted_score = weighted_score * correlation_modifier

    weighted_score = round(weighted_score, 1)

    # 4. Count aligned factors
    factor_scores = {
        "trend": trend_score,
        "momentum": momentum_score,
        "structure": structure_score,
        "order_flow": of_score,
        "volume": vol_score,
    }

    direction = _determine_direction(weighted_score)

    # Hard gates — force NO_TRADE on insufficient data quality
    blocked, gate_reason = _apply_hard_gates(adx, volume_ratio, atr, direction)
    if blocked:
        direction = "NO_TRADE"
        all_signals_extra = [f"BLOCKED: {gate_reason}"]
    else:
        all_signals_extra = []

    if direction == "LONG":
        factors_aligned = sum(1 for s in factor_scores.values() if s > 10)
    elif direction == "SHORT":
        factors_aligned = sum(1 for s in factor_scores.values() if s < -10)
    else:
        factors_aligned = 0

    # Confluence floor: require at least 2 factors meaningfully aligned
    if direction in ("LONG", "SHORT") and factors_aligned < 2:
        direction = "NO_TRADE"
        all_signals_extra = ["No trade: fewer than 2 factors aligned — insufficient confluence"]

    # 5. Order flow gate — check for contradictions
    order_flow_agrees = True
    has_divergence = False
    has_contra_divergence = False  # divergence that directly contradicts signal direction

    divergences = of_summary.get("divergences", [])
    if divergences:
        has_divergence = True

    if direction == "LONG" and of_score < -20:
        order_flow_agrees = False
    elif direction == "SHORT" and of_score > 20:
        order_flow_agrees = False

    # Detect directional divergence contradiction (used to hard-cap A+)
    for div in divergences:
        div_type = div.get("type", "")
        if direction == "LONG" and div_type == "BEARISH_DIVERGENCE":
            has_contra_divergence = True
            break
        elif direction == "SHORT" and div_type == "BULLISH_DIVERGENCE":
            has_contra_divergence = True
            break

    # Order flow contradiction is reflected in grade, not as a hard block

    # 6. Grade signal
    grade = _grade_signal(weighted_score, factors_aligned, order_flow_agrees, has_divergence)

    # Hard cap: A+ cannot survive a contradicting CVD divergence
    # (price makes new extreme but smart money doesn't confirm — high failure rate)
    if grade == "A+" and has_contra_divergence:
        grade = "A"
        all_signals_extra.append("A+ capped to A: Contradicting CVD divergence detected")

    # Dead zone downgrade: grade B in low-conviction sessions → C
    # session_modifier <= 0.70 = NY Lunch or overnight dead zone
    if grade == "B" and session_modifier <= 0.70:
        grade = "C"
        all_signals_extra.append(
            f"Grade B downgraded to C: dead zone session (modifier={session_modifier:.2f})"
        )

    # Downgrade direction on F grade only (C can still produce signals)
    if grade == "F":
        direction = "NO_TRADE"

    # 7. Build confluences list for frontend
    confluences = []
    for name, (fscore, fsignals) in [
        ("TREND", (trend_score, trend_signals)),
        ("MOMENTUM", (momentum_score, momentum_signals)),
        ("STRUCTURE", (structure_score, structure_signals)),
        ("ORDER_FLOW", (of_score, of_signals)),
        ("VOLUME", (vol_score, vol_signals)),
    ]:
        fdir = "BULLISH" if fscore > 10 else "BEARISH" if fscore < -10 else "NEUTRAL"
        confluences.append({
            "name": name,
            "score": fscore,
            "direction": fdir,
            "weight": weights[name.lower()],
            "signals": fsignals,
        })

    # Combine all signals
    all_signals = trend_signals + momentum_signals + structure_signals + of_signals + vol_signals + all_signals_extra

    # Add MTF confluence signal if relevant
    if mtf_multiplier != 1.0:
        all_signals.append(f"MTF Order Flow: {mtf_label} ({mtf_multiplier}x multiplier)")

    # Add session signal if relevant
    if session_modifier != 1.0:
        if session_modifier > 1.0:
            all_signals.append(f"Session: {session_label} (+{int((session_modifier - 1) * 100)}% boost)")
        else:
            all_signals.append(f"Session: {session_label} (-{int((1 - session_modifier) * 100)}% penalty)")

    # Add correlation signal if relevant
    if correlation_modifier != 1.0:
        if correlation_modifier > 1.0:
            all_signals.append(f"Intermarket: {correlation_label} (+{int((correlation_modifier - 1) * 100)}% boost)")
        else:
            all_signals.append(f"Intermarket: {correlation_label} (-{int((1 - correlation_modifier) * 100)}% penalty)")

    final_score = max(-100, min(100, int(weighted_score)))

    # Compute structure-aware SL/TP levels
    structure_levels = compute_structure_levels(ict_data, current_price, direction, atr)

    return {
        "score": final_score,
        "direction": direction,
        "signals": all_signals,
        "grade": grade,
        "regime": regime,
        "factors_aligned": factors_aligned,
        "order_flow_agrees": order_flow_agrees,
        "confluences": confluences,
        "factor_scores": factor_scores,
        "mtf_confluence_multiplier": mtf_multiplier,
        "mtf_confluence_label": mtf_label,
        "session_modifier": session_modifier,
        "session_label": session_label,
        "correlation_modifier": correlation_modifier,
        "correlation_label": correlation_label,
        "structure_levels": structure_levels,
    }


# ═══════════════════════════════════════════════════════════
#  STRUCTURE-AWARE SL/TP COMPUTATION
# ═══════════════════════════════════════════════════════════

def compute_structure_levels(ict_data, current_price, direction, atr):
    """
    Compute SL and TP levels based on ICT structure (order blocks, FVGs, swing points).

    For LONG: SL below nearest bullish support structure
    For SHORT: SL above nearest bearish resistance structure
    Falls back to ATR-based levels if no structure found.
    """
    result = {
        "suggested_sl": None,
        "suggested_tp1": None,
        "suggested_tp2": None,
        "sl_reference": "none",
        "fallback_used": True,
    }

    if not current_price or not atr or direction == "NO_TRADE":
        return result

    cp = float(current_price)
    atr_val = float(atr)
    buffer = 0.25 * atr_val

    if not ict_data:
        # Pure ATR fallback
        if direction == "LONG":
            result["suggested_sl"] = round(cp - 1.5 * atr_val, 2)
            result["suggested_tp1"] = round(cp + 2.0 * atr_val, 2)
            result["suggested_tp2"] = round(cp + 3.0 * atr_val, 2)
        elif direction == "SHORT":
            result["suggested_sl"] = round(cp + 1.5 * atr_val, 2)
            result["suggested_tp1"] = round(cp - 2.0 * atr_val, 2)
            result["suggested_tp2"] = round(cp - 3.0 * atr_val, 2)
        result["sl_reference"] = "ATR fallback (no ICT data)"
        return result

    order_blocks = ict_data.get("order_blocks", [])
    fair_value_gaps = ict_data.get("fair_value_gaps", [])
    swing_highs = [s.get("price", 0) for s in ict_data.get("recent_swing_highs", [])]
    swing_lows = [s.get("price", 0) for s in ict_data.get("recent_swing_lows", [])]

    if direction == "LONG":
        # SL: find nearest support below price (bullish OB bottom, bullish FVG bottom, swing low)
        support_levels = []
        for ob in order_blocks:
            if "bullish" in ob.get("type", "").lower() and ob.get("bottom", 0) < cp:
                support_levels.append(("OB", ob["bottom"]))
        for fvg in fair_value_gaps:
            if "bullish" in fvg.get("type", "").lower() and fvg.get("bottom", 0) < cp:
                support_levels.append(("FVG", fvg["bottom"]))
        for sl_price in swing_lows:
            if 0 < sl_price < cp:
                support_levels.append(("Swing Low", sl_price))

        if support_levels:
            # Use nearest support below price
            support_levels.sort(key=lambda x: x[1], reverse=True)
            ref_type, ref_price = support_levels[0]
            result["suggested_sl"] = round(ref_price - buffer, 2)
            result["sl_reference"] = f"{ref_type} at {ref_price:.2f}"
            result["fallback_used"] = False
        else:
            result["suggested_sl"] = round(cp - 1.5 * atr_val, 2)
            result["sl_reference"] = "ATR fallback (no support structure)"

        # TP: nearest resistance above price
        resistance_levels = []
        for ob in order_blocks:
            if "bearish" in ob.get("type", "").lower() and ob.get("top", 0) > cp:
                resistance_levels.append(ob["top"])
        for sh_price in swing_highs:
            if sh_price > cp:
                resistance_levels.append(sh_price)
        resistance_levels.sort()

        if len(resistance_levels) >= 2:
            result["suggested_tp1"] = round(resistance_levels[0], 2)
            result["suggested_tp2"] = round(resistance_levels[1], 2)
        elif len(resistance_levels) == 1:
            result["suggested_tp1"] = round(resistance_levels[0], 2)
            result["suggested_tp2"] = round(cp + 3.0 * atr_val, 2)
        else:
            result["suggested_tp1"] = round(cp + 2.0 * atr_val, 2)
            result["suggested_tp2"] = round(cp + 3.0 * atr_val, 2)

    elif direction == "SHORT":
        # SL: find nearest resistance above price (bearish OB top, bearish FVG top, swing high)
        resistance_levels = []
        for ob in order_blocks:
            if "bearish" in ob.get("type", "").lower() and ob.get("top", 0) > cp:
                resistance_levels.append(("OB", ob["top"]))
        for fvg in fair_value_gaps:
            if "bearish" in fvg.get("type", "").lower() and fvg.get("top", 0) > cp:
                resistance_levels.append(("FVG", fvg["top"]))
        for sh_price in swing_highs:
            if sh_price > cp:
                resistance_levels.append(("Swing High", sh_price))

        if resistance_levels:
            # Use nearest resistance above price
            resistance_levels.sort(key=lambda x: x[1])
            ref_type, ref_price = resistance_levels[0]
            result["suggested_sl"] = round(ref_price + buffer, 2)
            result["sl_reference"] = f"{ref_type} at {ref_price:.2f}"
            result["fallback_used"] = False
        else:
            result["suggested_sl"] = round(cp + 1.5 * atr_val, 2)
            result["sl_reference"] = "ATR fallback (no resistance structure)"

        # TP: nearest support below price
        support_levels = []
        for ob in order_blocks:
            if "bullish" in ob.get("type", "").lower() and ob.get("bottom", 0) < cp:
                support_levels.append(ob["bottom"])
        for sl_price in swing_lows:
            if 0 < sl_price < cp:
                support_levels.append(sl_price)
        support_levels.sort(reverse=True)

        if len(support_levels) >= 2:
            result["suggested_tp1"] = round(support_levels[0], 2)
            result["suggested_tp2"] = round(support_levels[1], 2)
        elif len(support_levels) == 1:
            result["suggested_tp1"] = round(support_levels[0], 2)
            result["suggested_tp2"] = round(cp - 3.0 * atr_val, 2)
        else:
            result["suggested_tp1"] = round(cp - 2.0 * atr_val, 2)
            result["suggested_tp2"] = round(cp - 3.0 * atr_val, 2)

    return result
