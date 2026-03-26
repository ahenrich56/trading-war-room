import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

import openai
import yfinance as yf
import pandas as pd
from whale_intel import TradFiWhaleDetector

# ─── Extracted Modules ──────────────────────────────────────
from indicators import _ema, _rsi, _macd, _atr, _adx, _vwap, _bollinger, _stoch_rsi, compute_indicators
from ict_analysis import detect_ict_concepts, format_ict_for_ai
from data_fetcher import (
    TICKER_MAP, CONTEXT_TICKERS, resolve_ticker, format_indicators_for_ai,
    TIMEFRAME_CONFIG, fetch_multi_timeframe_data, build_mtf_summary,
    fetch_market_context, get_economic_calendar,
)
from db import DB_PATH, _init_db, store_signal, get_learning_context, get_signal_history, report_outcome, get_outcomes, monitor_active_trades
from backtest import calculate_strategy_score, calculate_kelly, run_backtest
from order_flow import compute_order_flow_summary, format_order_flow_for_ai, compute_delta_series, compute_mtf_order_flow
from signal_scoring import calculate_enhanced_score

load_dotenv()

app = FastAPI(title="AI Trading War Room Backend")
executor = ThreadPoolExecutor(max_workers=4)
whale_detector = TradFiWhaleDetector()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KILO_API_KEY = os.getenv("KILO_API_KEY", "")

try:
    client = openai.AsyncOpenAI(
        api_key=KILO_API_KEY,
        base_url="https://api.kilo.ai/api/gateway"
    )
except Exception as e:
    print(f"Warning: OpenAI client init failed: {e}")
    client = None


# ═══════════════════════════════════════════════════════════
#  PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════

class AnalysisRequest(BaseModel):
    ticker: str
    timeframe: str
    riskProfile: str

class ChartDataRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"

class ChartRequest(BaseModel):
    ticker: str
    timeframe: str

class WatchlistRequest(BaseModel):
    tickers: list[str] = ["NQ1", "ES1", "YM1", "RTY1", "GC1", "CL1", "SI1", "ZB1"]
    timeframe: str = "5m"

class ConsensusRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"

class ICTRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"

class BacktestRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"
    lookback_days: int = 5

class OutcomeReport(BaseModel):
    ticker: str
    signal: str
    entry: float
    result: str  # WIN or LOSS
    pnl_pct: float
    notes: str = ""


# ═══════════════════════════════════════════════════════════
#  AI WRAPPER
# ═══════════════════════════════════════════════════════════

async def ask_ai(role: str, prompt: str, max_tokens: int = 300, learning_context: str = "") -> str:
    if not client:
        await asyncio.sleep(1)
        return f"[{role}] Mock response - missing API key."
    try:
        system_msg = f"You are a hedge fund {role}. Provide decisive, data-driven analysis. Reference exact indicator values provided. Be specific about price levels."
        if learning_context:
            system_msg += f"\n\n{learning_context}"
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error querying {role}: {str(e)}"


# ═══════════════════════════════════════════════════════════
#  TELEGRAM BOT ALERTS
# ═══════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

async def send_telegram_alert(signal_data: dict):
    """Send a formatted signal alert to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    try:
        sig = signal_data.get("signal", "UNKNOWN")
        ticker = signal_data.get("ticker", "???")
        tf = signal_data.get("timeframe", "?")
        confidence = signal_data.get("confidence", 0)
        entry = signal_data.get("entry_zone", {})
        sl = signal_data.get("stop_loss", 0)
        tps = signal_data.get("take_profit", [])
        rr = signal_data.get("risk_reward", 0)
        reasons = signal_data.get("reasons", [])
        regime = signal_data.get("market_regime", "unknown")

        emoji = "🟢" if sig == "LONG" else "🔴" if sig == "SHORT" else "⚪"

        tp_lines = ""
        for tp in tps:
            tp_lines += f"  TP{tp.get('level', '?')}: {tp.get('price', 0)}\n"

        reason_lines = "\n".join(f"  • {r}" for r in reasons[:3])

        message = (
            f"{emoji} *WAR ROOM SIGNAL*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"*{sig}* `{ticker}` on `{tf}`\n"
            f"Regime: `{regime}`\n\n"
            f"📍 *Entry:* `{entry.get('min', 0)} - {entry.get('max', 0)}`\n"
            f"🛑 *Stop:* `{sl}`\n"
            f"🎯 *Targets:*\n{tp_lines}\n"
            f"📊 R:R `{rr}` | Conf `{confidence}%`\n\n"
            f"💡 *Rationale:*\n{reason_lines}\n\n"
            f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
        )

        import httpx
        async with httpx.AsyncClient() as hclient:
            await hclient.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=5,
            )
    except Exception as e:
        print(f"Telegram alert failed: {e}")


# ═══════════════════════════════════════════════════════════
#  POST-AI SIGNAL VALIDATION
# ═══════════════════════════════════════════════════════════

def _validate_signal(signal_data, signal_grade, structure_levels, atr_val):
    """
    Post-AI safety net. Override signal to NO_TRADE if quality checks fail.
    This catches cases where the AI ignores prompt rules.
    """
    signal = signal_data.get("signal", "NO_TRADE")
    if signal not in ("LONG", "SHORT"):
        return signal_data

    overrides = []
    confidence = signal_data.get("confidence", 0)
    rr = signal_data.get("risk_reward", 0)

    # Gate 1: Minimum confidence
    if confidence < 25:
        overrides.append(f"Confidence {confidence}% < 25% minimum")

    # Gate 2: Minimum R:R
    if rr < 1.5:
        overrides.append(f"R:R {rr} < 1.5 minimum")

    # Gate 3: Grade enforcement (defense-in-depth)
    if signal_grade in ("C", "F"):
        overrides.append(f"Grade {signal_grade} requires NO_TRADE")

    # Gate 4: SL sanity check
    sl = signal_data.get("stop_loss", 0)
    entry_zone = signal_data.get("entry_zone", {})
    entry_mid = (entry_zone.get("min", 0) + entry_zone.get("max", 0)) / 2
    if sl and entry_mid and atr_val:
        sl_distance = abs(entry_mid - sl)
        if sl_distance > 3 * atr_val:
            overrides.append(f"SL distance {sl_distance:.1f} > 3x ATR ({3*atr_val:.1f})")
        if sl_distance < 0.3 * atr_val:
            overrides.append(f"SL distance {sl_distance:.1f} < 0.3x ATR ({0.3*atr_val:.1f})")

    # Gate 5: Validate SL against structure
    if structure_levels and not structure_levels.get("fallback_used"):
        suggested_sl = structure_levels.get("suggested_sl", 0)
        if suggested_sl and sl:
            if signal == "LONG" and sl > suggested_sl:
                overrides.append(f"SL {sl} above structure support {suggested_sl}")
            elif signal == "SHORT" and sl < suggested_sl:
                overrides.append(f"SL {sl} below structure resistance {suggested_sl}")

    if overrides:
        signal_data["signal"] = "NO_TRADE"
        signal_data["validation_overrides"] = overrides
        signal_data["original_signal"] = signal
        reasons = signal_data.get("reasons", [])
        reasons.append(f"OVERRIDDEN: {'; '.join(overrides)}")
        signal_data["reasons"] = reasons

    return signal_data


# ═══════════════════════════════════════════════════════════
#  MAIN ANALYSIS STREAM
# ═══════════════════════════════════════════════════════════

async def generate_analysis_stream(req: AnalysisRequest):
    ticker = req.ticker.upper()
    tf = req.timeframe
    risk = req.riskProfile

    def emit(marker: str, data):
        return f"data: [{marker}] {json.dumps(data)}\n\n"

    try:
        # ── 0. Fetch ALL data concurrently ──
        loop = asyncio.get_event_loop()
        mtf_data, market_context, econ_calendar, whale_alerts = await asyncio.gather(
            loop.run_in_executor(executor, fetch_multi_timeframe_data, ticker, tf),
            loop.run_in_executor(executor, fetch_market_context),
            loop.run_in_executor(executor, get_economic_calendar),
            loop.run_in_executor(executor, whale_detector.analyze_ticker, ticker),
        )

        mtf_summary = build_mtf_summary(mtf_data, ticker)
        primary = list(mtf_data["indicators"].values())[0] if mtf_data["indicators"] else {}
        current_price = primary.get("current_price", "UNKNOWN")

        # Order Flow + ICT from primary timeframe
        primary_df = mtf_data.get("dataframes", {}).get(tf) if "dataframes" in mtf_data else None
        ict_data = {}
        ict_text = ""
        order_flow_data = {}
        order_flow_text = ""
        if primary_df is not None and not primary_df.empty:
            # Compute order flow first so delta DF can validate ICT zones
            order_flow_data = compute_order_flow_summary(primary_df)
            order_flow_text = format_order_flow_for_ai(order_flow_data)
            delta_df = compute_delta_series(primary_df)
            ict_data = detect_ict_concepts(primary_df, order_flow_df=delta_df)
            ict_text = format_ict_for_ai(ict_data)

        # ── MTF Order Flow Confluence ──
        mtf_of = {}
        dataframes = mtf_data.get("dataframes", {})
        if dataframes:
            mtf_of = compute_mtf_order_flow(dataframes, tf)

        # Stream ICT, Order Flow, and Backtest data to frontend panels
        yield emit("ICT", {"ticker": ticker, "timeframe": tf, "ict": ict_data})
        yield emit("ORDER_FLOW", order_flow_data)
        yield emit("MTF_ORDER_FLOW", mtf_of)

        # ── Calculate Enhanced Strategy Score (5-Factor Confluence) ──
        enhanced = calculate_enhanced_score(primary, ict_data, order_flow_data, mtf_confluence=mtf_of)
        strat_score = enhanced["score"]
        strat_dir = enhanced["direction"]
        strat_reasons = enhanced["signals"]
        signal_grade = enhanced["grade"]
        market_regime = enhanced["regime"]
        confluences = enhanced["confluences"]
        factors_aligned = enhanced["factors_aligned"]
        order_flow_agrees = enhanced["order_flow_agrees"]

        # Format MTF order flow confluence for AI
        mtf_of_text = ""
        if mtf_of and mtf_of.get("total_count", 0) > 0:
            mtf_of_text = "═══ MTF ORDER FLOW CONFLUENCE ═══\n"
            for tf_key, bias in mtf_of.get("tf_biases", {}).items():
                cvd = mtf_of.get("tf_cvd", {}).get(tf_key, "FLAT")
                mtf_of_text += f"  {tf_key}: Delta={bias}, CVD={cvd}\n"
            mtf_of_text += f"  Confluence: {mtf_of['confluence_label']} ({mtf_of['confluence_multiplier']}x multiplier)\n"
            mtf_of_text += f"  Agreement: {mtf_of['agreement_count']}/{mtf_of['total_count']} timeframes aligned"

        full_data = f"{mtf_summary}\n\n{ict_text}\n\n{order_flow_text}\n\n{mtf_of_text}\n\n{market_context}\n\n{econ_calendar}"

        # ── 0a. Format Whale Alerts ──
        whale_text = ""
        if whale_alerts:
            whale_text = f"═══ SMART MONEY / WHALE FLOW ALERTS ═══\n"
            for w in whale_alerts:
                whale_text += f"  [{w.alert_type.upper()}] {w.details['label']}! Magnitude: {w.magnitude:.1f}x normal volume. Price direction: {w.details['price_change_pct']}. Confidence: {w.confidence:.0f}/100.\n"
            full_data += f"\n\n{whale_text}"
            yield emit("WHALE_ALERTS", [w.__dict__ for w in whale_alerts])

        # ── 0b. Fetch self-learning context from outcomes DB ──
        learning_ctx = get_learning_context()

        price_anchor = (
            f"\nCRITICAL: CURRENT LIVE PRICE of {ticker} is {current_price}. "
            f"ALL prices MUST be within realistic range of {current_price}. DO NOT hallucinate."
        )

        # ── 1. ANALYST TEAM ──
        analysts = {
            "FUNDAMENTAL_ANALYST": f"Analyze {ticker} fundamentals. Price: {current_price}.\n{mtf_summary}\n{market_context}",
            "SENTIMENT_ANALYST": f"Analyze sentiment for {ticker}. Price: {current_price}. Vol ratio: {primary.get('volume_ratio', 'N/A')}x. RSI: {primary.get('RSI_14', 'N/A')}.\n{market_context}",
            "NEWS_ANALYST": f"Analyze macro factors for {ticker}. Price: {current_price}.\n{market_context}\n{econ_calendar}",
            "TECHNICAL_ANALYST": f"Technical analysis for {ticker} using REAL computed indicators, Smart Money Concepts, AND Order Flow below. Reference exact values, mention structure (BOS/CHoCH), order blocks, FVGs, delta bias, CVD trend, volume profile (POC/VAH/VAL), and any divergences or absorption zones.\n{mtf_summary}\n{ict_text}\n{order_flow_text}{price_anchor}",
        }

        analyst_outputs = {}
        for role, prompt in analysts.items():
            text = await ask_ai(role, prompt, learning_context=learning_ctx)
            analyst_outputs[role] = text
            yield emit(role, {"text": text})

        # ── 2. RESEARCHER DEBATE ──
        context_str = json.dumps(analyst_outputs)

        bear_text = await ask_ai("BEAR_RESEARCHER",
            f"Using analyst data and REAL indicators: {context_str}\n{full_data}\n"
            f"Argue BEARISH case against {ticker} at {current_price}. Use specific indicator values.", 300, learning_context=learning_ctx)
        yield emit("BEAR_RESEARCHER", {"text": bear_text})

        bull_text = await ask_ai("BULL_RESEARCHER",
            f"Using analyst data and REAL indicators: {context_str}\n{full_data}\n"
            f"Argue BULLISH case for {ticker} at {current_price}. Use specific indicator values.", 300, learning_context=learning_ctx)
        yield emit("BULL_RESEARCHER", {"text": bull_text})

        # ── 3. TRADER & RISK ──
        trader_text = await ask_ai("TRADER_DECISION",
            f"Review bull/bear for {ticker}. Price: {current_price}. "
            f"Strategy says: {strat_dir} (score {strat_score}). AI must agree with strategy direction or choose NO_TRADE. "
            f"ATR={primary.get('ATR_14', 'N/A')}, BB upper={primary.get('BB_upper', 'N/A')}, "
            f"BB lower={primary.get('BB_lower', 'N/A')}, VWAP={primary.get('VWAP', 'N/A')}. "
            f"Timeframe: {tf}. Be decisive.", 250, learning_context=learning_ctx)
        yield emit("TRADER_DECISION", {"text": trader_text})

        atr_val = primary.get("ATR_14", 0)
        risk_text = await ask_ai("RISK_MANAGER",
            f"Review trader plan for {ticker} at {current_price} ({strat_dir}). ATR(14)={atr_val}. "
            f"Risk profile: {risk}.\n{market_context}\nApprove? Size recommendation.", 250, learning_context=learning_ctx)
        yield emit("RISK_MANAGER", {"text": risk_text})

        # ── 4. SIGNAL ENGINE ──
        atr_num = float(atr_val) if atr_val and atr_val != "N/A" else (float(current_price) * 0.005 if isinstance(current_price, (int, float)) else 50)
        cp = float(current_price) if isinstance(current_price, (int, float)) else 0

        # Get structure-aware SL/TP levels
        structure_levels = enhanced.get("structure_levels", {})
        suggested_sl = structure_levels.get("suggested_sl", "N/A")
        suggested_tp1 = structure_levels.get("suggested_tp1", "N/A")
        suggested_tp2 = structure_levels.get("suggested_tp2", "N/A")
        sl_reference = structure_levels.get("sl_reference", "none")

        # Format ICT structure for prompt
        ict_obs_text = ""
        for ob in ict_data.get("order_blocks", [])[-4:]:
            ict_obs_text += f"  {ob.get('type','?')} OB: {ob.get('bottom',0):.2f}-{ob.get('top',0):.2f} (strength: {ob.get('strength','?')})\n"
        ict_fvgs_text = ""
        for fvg in ict_data.get("fair_value_gaps", [])[-4:]:
            ict_fvgs_text += f"  {fvg.get('type','?')} FVG: {fvg.get('bottom',0):.2f}-{fvg.get('top',0):.2f} (strength: {fvg.get('strength','?')})\n"

        json_prompt = f"""
Based on all context for {ticker} on {tf}, risk profile '{risk}':

CRITICAL PRICE DATA:
- Current price: {current_price}
- ATR(14): {atr_val}
- RSI(14): {primary.get('RSI_14', 'N/A')}
- MACD histogram: {primary.get('MACD_histogram', 'N/A')}
- EMA 9/21 cross: {primary.get('EMA_9_21_cross', 'N/A')}
- Price vs VWAP: {primary.get('price_vs_VWAP', 'N/A')}
- BB upper: {primary.get('BB_upper', 'N/A')}
- BB lower: {primary.get('BB_lower', 'N/A')}
- ADX: {primary.get('ADX', 'N/A')}

ORDER FLOW DATA:
- Delta Bias: {order_flow_data.get('summary', {}).get('overall_delta_bias', 'N/A')}
- CVD Trend: {order_flow_data.get('summary', {}).get('cvd_trend', 'N/A')}
- POC: {order_flow_data.get('summary', {}).get('poc', 'N/A')}
- VAH: {order_flow_data.get('summary', {}).get('vah', 'N/A')}
- VAL: {order_flow_data.get('summary', {}).get('val', 'N/A')}
- Divergences: {len(order_flow_data.get('divergences', []))}
- Absorptions: {len(order_flow_data.get('absorptions', []))}
- VWAP Deviation: {order_flow_data.get('summary', {}).get('vwap_deviation', 0)}σ

ICT STRUCTURE LEVELS (use these for SL/TP placement):
- Order Blocks:
{ict_obs_text if ict_obs_text else '  None detected'}
- Fair Value Gaps:
{ict_fvgs_text if ict_fvgs_text else '  None detected'}
- Suggested SL (structure-based): {suggested_sl} (ref: {sl_reference})
- Suggested TP1: {suggested_tp1}
- Suggested TP2: {suggested_tp2}

ENHANCED STRATEGY SCORING (5-Factor Confluence):
- Strategy Direction: {strat_dir}
- Strategy Score: {strat_score} (-100 to +100)
- Signal Grade: {signal_grade} (A+=highest, F=reject)
- Market Regime: {market_regime}
- Factors Aligned: {factors_aligned}/5
- Order Flow Agrees: {order_flow_agrees}
- Key Drivers: {', '.join(strat_reasons[:6])}

RULES:
- YOUR FINAL SIGNAL MUST EXACTLY MATCH THE STRATEGY DIRECTION ({strat_dir}).
- IF SIGNAL GRADE IS 'F' OR 'C', USE 'NO_TRADE'.
- IF THE RISK IS TOO HIGH OR CONTEXT IS BAD, YOU MAY DOWNGRADE TO 'NO_TRADE'.
- YOU MAY NEVER CALL A 'LONG' IF THE STRATEGY IS 'SHORT', OR VICE VERSA.
- Confidence MUST be >= 25 for any trade signal (LONG/SHORT). If unsure, use NO_TRADE.
- R:R (risk_reward) MUST be >= 1.5 for any trade signal.
- SL MUST be placed beyond the nearest ICT structure level (order block or FVG). Use the suggested SL above.
- Entry: within 0.5x ATR of {current_price}
- TP1/TP2: Use suggested TP levels above, or nearest structural targets

Output ONLY valid JSON, no markdown:
{{
    "ticker": "{ticker}",
    "timestamp_utc": "{datetime.utcnow().isoformat()}Z",
    "timeframe": "{tf}",
    "market_regime": "{market_regime}",
    "signal": "LONG|SHORT|NO_TRADE",
    "signal_grade": "{signal_grade}",
    "entry_zone": {{"min": 0, "max": 0}},
    "stop_loss": 0,
    "take_profit": [{{"level": 1, "price": 0}}, {{"level": 2, "price": 0}}],
    "risk_reward": 0,
    "confidence": 0,
    "position_size_pct": 0,
    "max_hold_minutes": 0,
    "invalidation_condition": "string",
    "reasons": ["string", "string"],
    "agent_agreement_score": 0,
    "tv_alert": "TICKER={ticker};TF={tf};SIG=...;ENTRY=...;SL=...;TP1=...;TP2=...;CONF=...",
    "indicators_used": {{"RSI_14": {primary.get('RSI_14', 'null')}, "MACD_histogram": {primary.get('MACD_histogram', 'null')}, "ATR_14": {primary.get('ATR_14', 'null')}, "ADX": {primary.get('ADX', 'null')}}}
}}
"""
        signal_text = await ask_ai("SIGNAL_ENGINE", json_prompt, 600, learning_context=learning_ctx)
        clean_json = signal_text.replace("```json", "").replace("```", "").strip()

        try:
            signal_data = json.loads(clean_json)
        except json.JSONDecodeError:
            signal_data = {
                "ticker": ticker,
                "timestamp_utc": datetime.utcnow().isoformat() + "Z",
                "timeframe": tf,
                "market_regime": "range_day",
                "signal": "NO_TRADE",
                "entry_zone": {"min": 0, "max": 0},
                "stop_loss": 0,
                "take_profit": [{"level": 1, "price": 0}],
                "risk_reward": 0,
                "confidence": 0,
                "position_size_pct": 0,
                "max_hold_minutes": 0,
                "invalidation_condition": "AI failed to return valid JSON",
                "reasons": ["Signal engine parse error. Trade aborted for safety."],
                "agent_agreement_score": 0,
                "tv_alert": f"TICKER={ticker};TF={tf};SIG=NO_TRADE;CONF=0;"
            }

        # ── Post-AI Signal Validation ──
        signal_data = _validate_signal(signal_data, signal_grade, structure_levels, atr_num)

        # Inject enhanced scoring metadata into signal
        signal_data["signal_grade"] = signal_grade
        signal_data["market_regime"] = market_regime
        signal_data["confluences"] = confluences
        signal_data["factors_aligned"] = factors_aligned
        signal_data["order_flow_agrees"] = order_flow_agrees
        signal_data["order_flow_bias"] = order_flow_data.get("summary", {}).get("overall_delta_bias", "NEUTRAL") if order_flow_data else "NEUTRAL"
        signal_data["mtf_confluence_label"] = enhanced.get("mtf_confluence_label", "NEUTRAL")
        signal_data["mtf_confluence_multiplier"] = enhanced.get("mtf_confluence_multiplier", 1.0)
        signal_data["structure_levels"] = structure_levels

        # Store signal in history and send Telegram alert
        await store_signal(signal_data)
        await send_telegram_alert(signal_data)

        yield emit("SIGNAL_ENGINE", signal_data)

    except Exception as e:
        yield emit("ERROR", {"text": f"Backend stream failed: {str(e)}"})


# Initialize DB on import
_init_db()


# ═══════════════════════════════════════════════════════════
#  CHART DATA ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/chart-data")
async def get_chart_data(req: ChartDataRequest):
    try:
        ticker = req.ticker.upper()
        tf = req.timeframe

        loop = asyncio.get_event_loop()
        mtf_data = await loop.run_in_executor(executor, fetch_multi_timeframe_data, ticker, tf)

        if "dataframes" not in mtf_data or tf not in mtf_data["dataframes"]:
            return {"candles": []}

        df = mtf_data["dataframes"][tf]

        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "time": int(idx.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"])
            })

        # Compute order flow for chart overlays
        of_data = compute_order_flow_summary(df) if len(df) >= 20 else {}

        return {
            "candles": candles,
            "order_flow": {
                "delta_bars": of_data.get("delta_bars", []),
                "cvd": of_data.get("cvd", []),
                "volume_profile": of_data.get("volume_profile", {}),
                "vwap_bands": of_data.get("vwap_bands", {}),
            } if of_data else {}
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "candles": []}


@app.post("/api/v1/chart-data-full")
async def chart_data_endpoint(request: ChartRequest):
    """Return OHLCV data + indicator overlays for TradingView Lightweight Charts."""
    ticker = request.ticker.upper()
    yf_symbol = resolve_ticker(ticker)

    tf_map = {
        "1m": ("1m", "1d"), "2m": ("2m", "5d"), "5m": ("5m", "5d"),
        "15m": ("15m", "5d"), "1h": ("1h", "30d"), "4h": ("1h", "30d"),
    }
    interval, period = tf_map.get(request.timeframe, ("5m", "5d"))

    try:
        tk = yf.Ticker(yf_symbol)
        df = tk.history(period=period, interval=interval)

        if df.empty:
            return {"error": "No data", "candles": [], "indicators": {}}

        # Build candles array for TradingView
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                "time": int(idx.timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        # Compute indicator overlays
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        ema9 = _ema(close, 9)
        ema21 = _ema(close, 21)
        vwap_series = ((high + low + close) / 3 * volume).cumsum() / volume.cumsum()

        # Build overlay arrays
        ema9_data = [{"time": int(idx.timestamp()), "value": round(float(v), 2)}
                     for idx, v in ema9.items() if not pd.isna(v)]
        ema21_data = [{"time": int(idx.timestamp()), "value": round(float(v), 2)}
                      for idx, v in ema21.items() if not pd.isna(v)]
        vwap_data = [{"time": int(idx.timestamp()), "value": round(float(v), 2)}
                     for idx, v in vwap_series.items() if not pd.isna(v)]

        # BB bands
        bb = _bollinger(close)

        # Order flow data
        of_data = compute_order_flow_summary(df) if len(df) >= 20 else {}

        return {
            "candles": candles,
            "indicators": {
                "ema9": ema9_data,
                "ema21": ema21_data,
                "vwap": vwap_data,
                "bb": bb,
            },
            "order_flow": {
                "delta_bars": of_data.get("delta_bars", []),
                "cvd": of_data.get("cvd", []),
                "volume_profile": of_data.get("volume_profile", {}),
                "vwap_bands": of_data.get("vwap_bands", {}),
                "summary": of_data.get("summary", {}),
            } if of_data else {},
            "ticker": ticker,
            "symbol": yf_symbol,
        }

    except Exception as e:
        return {"error": str(e), "candles": [], "indicators": {}}


# ═══════════════════════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/analyze")
async def analyze_endpoint(request: AnalysisRequest):
    return StreamingResponse(
        generate_analysis_stream(request),
        media_type="text/event-stream"
    )

@app.get("/api/v1/signals")
async def signal_history_endpoint(limit: int = 20):
    return get_signal_history(limit)


# ═══════════════════════════════════════════════════════════
#  WATCHLIST SCANNER
# ═══════════════════════════════════════════════════════════

def quick_scan_ticker(ticker: str, timeframe: str) -> dict:
    """Fast indicator-only scan (no AI) for watchlist ranking."""
    try:
        yf_symbol = resolve_ticker(ticker)
        tf_map = {
            "1m": ("1m", "1d"), "5m": ("5m", "5d"),
            "15m": ("15m", "5d"), "1h": ("1h", "30d"),
        }
        interval, period = tf_map.get(timeframe, ("5m", "5d"))

        tk = yf.Ticker(yf_symbol)
        df = tk.history(period=period, interval=interval)

        if df.empty or len(df) < 20:
            return {"ticker": ticker, "error": "No data", "score": 0}

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        current_price = round(float(close.iloc[-1]), 2)
        rsi = _rsi(close, 14)
        macd = _macd(close)
        atr = _atr(high, low, close, 14)
        adx = _adx(high, low, close, 14)
        ema9 = round(float(_ema(close, 9).iloc[-1]), 2)
        ema21 = round(float(_ema(close, 21).iloc[-1]), 2)

        # Volume ratio
        avg_vol = volume.rolling(20).mean()
        vol_ratio = round(float(volume.iloc[-1]) / float(avg_vol.iloc[-1]), 2) if not pd.isna(avg_vol.iloc[-1]) and float(avg_vol.iloc[-1]) > 0 else 1.0

        # VWAP
        try:
            vwap = _vwap(high, low, close, volume)
        except:
            vwap = current_price

        hist = macd.get("MACD_histogram")

        # Build indicators dict for enhanced scorer
        indicators = compute_indicators(df)

        # Order flow (lightweight — skip if too few bars)
        of_data = compute_order_flow_summary(df) if len(df) >= 20 else {}

        # Enhanced scoring
        enhanced = calculate_enhanced_score(indicators, order_flow_data=of_data)
        score = enhanced["score"]
        direction = enhanced["direction"]
        grade = enhanced["grade"]

        direction = "NEUTRAL" if direction == "NO_TRADE" else direction

        return {
            "ticker": ticker,
            "symbol": yf_symbol,
            "price": current_price,
            "direction": direction,
            "score": max(-100, min(100, score)),
            "grade": grade,
            "regime": enhanced["regime"],
            "rsi": rsi,
            "macd_hist": hist,
            "adx": adx,
            "ema_cross": "BULLISH" if ema9 > ema21 else "BEARISH",
            "vol_ratio": vol_ratio,
            "atr": atr,
            "order_flow_bias": of_data.get("summary", {}).get("overall_delta_bias", "NEUTRAL") if of_data else "NEUTRAL",
            "signals": enhanced["signals"][:4],
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e), "score": 0}


@app.post("/api/v1/watchlist")
async def watchlist_scan(request: WatchlistRequest):
    """Scan multiple tickers and rank by signal strength."""
    loop = asyncio.get_event_loop()

    tasks = [
        loop.run_in_executor(executor, quick_scan_ticker, t, request.timeframe)
        for t in request.tickers
    ]
    results = await asyncio.gather(*tasks)

    results = sorted(results, key=lambda x: abs(x.get("score", 0)), reverse=True)
    best = results[0] if results else None

    return {
        "tickers": results,
        "best_opportunity": best,
        "scanned_at": datetime.utcnow().isoformat() + "Z",
        "timeframe": request.timeframe,
    }


# ═══════════════════════════════════════════════════════════
#  MULTI-MODEL CONSENSUS
# ═══════════════════════════════════════════════════════════

CONSENSUS_MODELS = [
    "gpt-4o-mini",
    "claude-3-5-haiku-20241022",
    "gemini-2.0-flash",
]

async def ask_model(model: str, prompt: str) -> dict:
    """Query a specific model for a signal verdict."""
    if not client:
        return {"model": model, "signal": "NO_TRADE", "confidence": 0, "error": "No API key"}

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=200,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "You are a trading signal engine. Output ONLY valid JSON with keys: signal (LONG/SHORT/NO_TRADE), confidence (0-100), entry (number), stop_loss (number), take_profit (number), reason (string). No markdown."},
                {"role": "user", "content": prompt}
            ]
        )
        text = response.choices[0].message.content
        clean = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
        data["model"] = model
        return data
    except json.JSONDecodeError:
        return {"model": model, "signal": "NO_TRADE", "confidence": 0, "error": "JSON parse failed"}
    except Exception as e:
        return {"model": model, "signal": "NO_TRADE", "confidence": 0, "error": str(e)[:100]}


@app.post("/api/v1/consensus")
async def multi_model_consensus(request: ConsensusRequest):
    """Run the same signal prompt through multiple AI models and aggregate."""
    ticker = request.ticker.upper()
    tf = request.timeframe

    loop = asyncio.get_event_loop()
    scan = await loop.run_in_executor(executor, quick_scan_ticker, ticker, tf)

    if "error" in scan:
        return {"error": scan["error"], "verdicts": [], "consensus": "NO_TRADE"}

    prompt = f"""
Analyze {ticker} for a {tf} trading signal.
Current price: {scan['price']}
RSI(14): {scan.get('rsi', 'N/A')}
MACD hist: {scan.get('macd_hist', 'N/A')}
ADX: {scan.get('adx', 'N/A')}
EMA cross: {scan.get('ema_cross', 'N/A')}
Volume ratio: {scan.get('vol_ratio', 'N/A')}x
ATR: {scan.get('atr', 'N/A')}

Output JSON: {{"signal":"LONG|SHORT|NO_TRADE","confidence":0-100,"entry":{scan['price']},"stop_loss":0,"take_profit":0,"reason":"string"}}
"""

    tasks = [ask_model(model, prompt) for model in CONSENSUS_MODELS]
    verdicts = await asyncio.gather(*tasks)

    signals = [v.get("signal", "NO_TRADE") for v in verdicts]
    long_count = signals.count("LONG")
    short_count = signals.count("SHORT")
    no_trade_count = signals.count("NO_TRADE")

    if long_count >= 2:
        consensus = "LONG"
    elif short_count >= 2:
        consensus = "SHORT"
    else:
        consensus = "NO_TRADE"

    avg_confidence = sum(v.get("confidence", 0) for v in verdicts) / max(len(verdicts), 1)

    max_agreement = max(long_count, short_count, no_trade_count)
    agreement_pct = round((max_agreement / len(verdicts)) * 100)

    return {
        "ticker": ticker,
        "timeframe": tf,
        "consensus": consensus,
        "agreement": f"{max_agreement}/{len(verdicts)}",
        "agreement_pct": agreement_pct,
        "avg_confidence": round(avg_confidence),
        "verdicts": verdicts,
        "models_used": CONSENSUS_MODELS,
        "scanned_at": datetime.utcnow().isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════
#  ICT ENDPOINT
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/ict")
async def ict_endpoint(request: ICTRequest):
    """Return ICT/Smart Money Concepts analysis for a ticker."""
    ticker = request.ticker.upper()
    yf_symbol = resolve_ticker(ticker)
    tf_map = {
        "1m": ("1m", "1d"), "5m": ("5m", "5d"),
        "15m": ("15m", "5d"), "1h": ("1h", "30d"),
    }
    interval, period = tf_map.get(request.timeframe, ("5m", "5d"))

    try:
        tk = yf.Ticker(yf_symbol)
        df = tk.history(period=period, interval=interval)
        if df.empty:
            return {"error": "No data", "ict": {}}

        ict_data = detect_ict_concepts(df)
        return {"ticker": ticker, "timeframe": request.timeframe, "ict": ict_data}
    except Exception as e:
        return {"error": str(e), "ict": {}}


# ═══════════════════════════════════════════════════════════
#  ORDER FLOW ENDPOINT
# ═══════════════════════════════════════════════════════════

class OrderFlowRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"

@app.post("/api/v1/order-flow")
async def order_flow_endpoint(request: OrderFlowRequest):
    """Return full order flow analysis for a ticker."""
    ticker = request.ticker.upper()
    yf_symbol = resolve_ticker(ticker)
    tf_map = {
        "1m": ("1m", "1d"), "5m": ("5m", "5d"),
        "15m": ("15m", "5d"), "1h": ("1h", "30d"),
    }
    interval, period = tf_map.get(request.timeframe, ("5m", "5d"))

    try:
        loop = asyncio.get_event_loop()
        tk = yf.Ticker(yf_symbol)
        df = await loop.run_in_executor(executor, lambda: tk.history(period=period, interval=interval))
        if df.empty or len(df) < 20:
            return {"error": "Insufficient data", "order_flow": {}}

        of_data = compute_order_flow_summary(df)
        return {"ticker": ticker, "timeframe": request.timeframe, "order_flow": of_data}
    except Exception as e:
        return {"error": str(e), "order_flow": {}}


# ═══════════════════════════════════════════════════════════
#  BACKTEST & OUTCOMES ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.post("/api/v1/backtest")
async def backtest_endpoint(request: BacktestRequest):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_backtest, request.ticker, request.timeframe, request.lookback_days)
    return result

@app.post("/api/v1/outcomes/report")
async def report_outcome_endpoint(report: OutcomeReport):
    return report_outcome(report.dict())

@app.get("/api/v1/outcomes")
async def get_outcomes_endpoint():
    return get_outcomes()


# ═══════════════════════════════════════════════════════════
#  WHALE ALERTS ENDPOINT
# ═══════════════════════════════════════════════════════════

@app.get("/api/v1/whale-alerts")
async def get_whale_alerts(ticker: str):
    """Fetch unusual volume and smart money alerts for a specific ticker."""
    loop = asyncio.get_event_loop()
    alerts = await loop.run_in_executor(executor, whale_detector.analyze_ticker, ticker.upper())
    return {"ticker": ticker.upper(), "alerts": [w.__dict__ for w in alerts]}


# ═══════════════════════════════════════════════════════════
#  STARTUP & HEALTH
# ═══════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application launch."""
    asyncio.create_task(monitor_active_trades(executor, resolve_ticker))


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "war-room-ai", "version": "6.0-order-flow"}
