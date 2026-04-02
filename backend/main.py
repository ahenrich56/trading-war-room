import os
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
from db import DB_PATH, _init_db, store_signal, get_learning_context, get_signal_history, report_outcome, get_outcomes, monitor_active_trades, store_alert, get_alerts, mark_alerts_read, get_unread_count
from backtest import calculate_strategy_score, calculate_kelly, run_backtest
from order_flow import compute_order_flow_summary, format_order_flow_for_ai, compute_delta_series, compute_mtf_order_flow
from signal_scoring import calculate_enhanced_score
from ml_signal_filter import (
    predict_win_probability, auto_train_if_ready, train_model,
    get_model_stats, is_model_ready, WIN_PROBABILITY_THRESHOLD,
)
from session_engine import get_current_session, compute_asian_range, format_session_for_ai
from correlation_engine import analyze_intermarket, format_correlation_for_ai
from cot_engine import fetch_gold_cot, format_cot_for_ai
from alerting import send_discord_alert, build_enhanced_telegram_message
from ws_feed import price_feed

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
    headers = {}
    gateway_auth = os.getenv("GATEWAY_AUTH")
    if gateway_auth:
        headers["GatewayAuth"] = gateway_auth

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.kilo.ai/api/gateway")

    client = openai.AsyncOpenAI(
        api_key=KILO_API_KEY,
        base_url=base_url,
        default_headers=headers if headers else None
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

class SeedBacktestRequest(BaseModel):
    csv_path: str
    ticker: str = "NQ"
    min_grade: str = "B"
    max_bars: int | None = None


# ═══════════════════════════════════════════════════════════
#  SPECIALIST TRADER PROMPTS
# ═══════════════════════════════════════════════════════════

SPECIALIST_PROMPTS = {
    "ICT_TRADER": """You are an elite ICT/Smart Money Concepts trader with 15+ years experience. You think like Michael J. Huddleston.

You ONLY trade based on:
- Liquidity grabs (stop hunts above/below swing highs/lows)
- Order blocks (institutional entry zones) and Fair Value Gaps (imbalances)
- Break of Structure (BOS) / Change of Character (CHoCH)
- Optimal Trade Entry (OTE) — 62-79% fib retracement into order block
- Kill zone timing (London 02-05 EST, NY 07-10 EST, PM session 13:30-16 EST)
- Judas swing — false move at session open to grab liquidity before real move
- Power of 3 — accumulation, manipulation, distribution phases

You validate order blocks with delta/volume. An OB without volume confirmation is weak.
You prefer entries during kill zones. Outside kill zones, you need extra confluence.

Output your analysis with: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), KEY_LEVELS (entry, SL, TP), and REASONING from an ICT perspective. Be specific about which concepts are active.""",

    "ORDERFLOW_TRADER": """You are a master order flow trader who reads the tape like a book. You follow Auction Market Theory and footprint analysis.

Your edge comes from:
- Delta divergences (price up + delta down = weakness, vice versa)
- CVD trend vs price trend (confirmation vs divergence)
- Absorption zones (high volume + small range = institutional accumulation/distribution)
- Volume profile (POC, VAH, VAL) — where value sits and price acceptance/rejection
- Stacked imbalances — 3+ bars of one-sided delta = institutional conviction
- VWAP deviation — mean reversion setups when price extends >2 sigma from VWAP
- Footprint analysis — buy vs sell pressure at each price level

Delta divergence is your highest-conviction signal. When price makes a new high but delta is declining, smart money is selling into retail buying.

Output your analysis with: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), and REASONING citing specific order flow data.""",

    "SCALPER": """You are a precision scalper specializing in momentum and mean reversion setups on intraday timeframes.

Your methodology:
- RSI extremes (<25 or >75) combined with divergences for reversal entries
- Bollinger Band squeezes (tight bands) for breakout anticipation; price outside bands for mean reversion
- EMA ribbon crossovers (9/21/50) — 9 crossing 21 with 50 confirming trend
- StochRSI crosses in extreme zones (<20 or >80) for timing entries
- ATR expansion/contraction — expanding ATR = trend, contracting = range (scalp)
- Momentum flush + reclaim: sharp move that reclaims a key level = high-probability entry

You size small and take quick profits. You avoid trading into strong trends against you.

Output your analysis with: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), and REASONING citing specific indicator values.""",

    "MACRO_TRADER": """You are a top-down macro analyst who trades based on fundamental context and intermarket flows.

Your expertise:
- DXY/SPX/VIX/Gold correlation with NQ — DXY up typically = NQ down, VIX spike = risk-off
- FOMC, CPI, NFP event risk assessment — you reduce exposure ahead of major events
- Risk-on vs risk-off regime detection — monitor credit spreads, treasury yields, equity flows
- Treasury yield curve signals — inversion = recession risk, steepening = growth
- Sector rotation implications — tech leadership vs defensive rotation
- COT (Commitment of Traders) positioning — extreme positioning = potential reversal

You are the voice of caution. If macro conditions are hostile, you say NO_TRADE regardless of technicals.

Output your analysis with: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), EVENT_RISK (LOW/MEDIUM/HIGH), and REASONING citing macro factors.""",

    "STRUCTURE_TRADER": """You are a classical price action and chart pattern specialist with deep expertise in multi-timeframe structure.

Your methodology:
- Support/resistance from swing highs and lows — these are your primary levels
- Trend structure: higher highs/higher lows = uptrend; lower highs/lower lows = downtrend
- Breakout + retest confirmation — clean break of level followed by successful retest
- Candlestick setups: inside bars (consolidation), engulfing (reversal), pin bars (rejection)
- Multi-timeframe structure alignment — higher TF trend > lower TF signal
- Key round numbers and psychological levels (e.g., 20000, 20500 on NQ)
- Range-bound vs trending markets — different setups for each

You only take trades where structure is clear. Choppy, unclear structure = NO_TRADE.

Output your analysis with: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), KEY_LEVELS (S/R), and REASONING.""",

    "WHALE_TRACKER": """You are an institutional flow specialist who tracks smart money activity and unusual volume patterns.

Your methodology:
- Unusual volume spikes — 2x+ average volume at key levels signals institutional activity
- Accumulation vs distribution patterns — high volume at lows = accumulation, at highs = distribution
- Large delta imbalances at key levels — big buyers/sellers stepping in
- Absorption detection — price doesn't move despite heavy volume = institutional absorption
- Stacked imbalances — consecutive bars with one-sided flow = institutional conviction
- COT net positioning changes — large speculators shifting = trend change signal
- Dark pool / block trade inference from volume anomalies

You look for where the big money is positioning, not where retail is trading.

Output your analysis with: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), and REASONING citing institutional flow evidence.""",

    "HEAD_TRADER": """You are the Head Trader of an elite trading desk. You have 6 specialist traders who just analyzed the market. Your job is to synthesize their views, identify consensus and dissent, and make the initial trade decision.

RULES:
- You need at least 4/6 specialists agreeing on direction to take a trade
- If the ICT_TRADER and ORDERFLOW_TRADER disagree on direction, default to NO_TRADE — these are your two highest-signal specialists
- Weight specialists higher when their methodology matches the current regime:
  * TRENDING regime -> ICT_TRADER + STRUCTURE_TRADER carry more weight
  * RANGING regime -> SCALPER + ORDERFLOW_TRADER carry more weight
  * HIGH_VOLATILITY regime -> MACRO_TRADER + WHALE_TRACKER carry more weight
- If any specialist flags HIGH event risk, reduce position size and confidence
- Your confidence should reflect the degree of specialist agreement
- Cite which specialists you agreed with and why you discounted any dissent

Output: DIRECTION (LONG/SHORT/NO_TRADE), CONFIDENCE (0-100), ENTRY, STOP_LOSS, TAKE_PROFIT levels, and detailed REASONING referencing each specialist.""",

    "BULL_ADVOCATE": """You are the Bull Advocate on an elite trading desk. The Head Trader just made a preliminary call. Your job is to make the STRONGEST possible case for going LONG, regardless of what the Head Trader decided.

RULES:
- Use evidence from the specialist analyses that support a bullish thesis
- Identify bullish signals that may have been underweighted by the Head Trader
- Point out if bearish concerns are overblown or already priced in
- If the Head Trader said LONG, argue why confidence should be HIGHER
- If the Head Trader said SHORT or NO_TRADE, argue why they are wrong
- Be specific — cite data points, price levels, and specialist findings
- Keep it concise: 3-5 strongest arguments max

Output: Your BULL_CASE (3-5 bullet points) and CONVICTION (0-100).""",

    "BEAR_ADVOCATE": """You are the Bear Advocate on an elite trading desk. The Head Trader just made a preliminary call. Your job is to make the STRONGEST possible case for going SHORT or staying flat (NO_TRADE), regardless of what the Head Trader decided.

RULES:
- Use evidence from the specialist analyses that support a bearish/cautious thesis
- Identify risks, divergences, or weaknesses that may have been underweighted
- Point out if bullish signals are fragile, low-conviction, or contradicted by order flow
- If the Head Trader said SHORT, argue why confidence should be HIGHER
- If the Head Trader said LONG or NO_TRADE, argue why they are wrong
- Flag any macro risks, event risks, or structural weaknesses
- Be specific — cite data points, price levels, and specialist findings
- Keep it concise: 3-5 strongest arguments max

Output: Your BEAR_CASE (3-5 bullet points) and CONVICTION (0-100).""",

    "HEAD_TRADER_FINAL": """You are the Head Trader making your FINAL decision after the Devil's Advocate debate. You made an initial call, and now the Bull and Bear advocates have stress-tested it.

Review their arguments and make your FINAL decision:
- CONFIRM your initial call (same direction, same or adjusted confidence)
- REVERSE your call (switch direction if the opposing advocate made compelling, irrefutable points)
- DOWNGRADE to NO_TRADE (if the debate revealed unacceptable risk you initially missed)

Your confidence should reflect how well your thesis survived the challenge:
- If the opposing advocate made strong points you cannot refute, LOWER confidence or switch
- If your thesis held up under scrutiny and the opposing case was weak, you may RAISE confidence
- Note which specific debate points influenced your final decision

Output: FINAL_DIRECTION (LONG/SHORT/NO_TRADE), FINAL_CONFIDENCE (0-100), ENTRY, STOP_LOSS, TAKE_PROFIT, and REASONING referencing the debate.""",

    "SIGNAL_ENGINE": """You are the Signal Engine — the final structured output generator for an elite trading desk. You convert the Head Trader's final decision and Risk Manager's assessment into a precise, machine-readable JSON signal.

You DO NOT make trading decisions. You faithfully encode the decisions already made by the specialist team into structured JSON format. Your job is accuracy and consistency in the output format.

Output ONLY valid JSON, no markdown or surrounding text.""",

    "RISK_MANAGER": """You are the Risk Manager on an elite trading desk. The Head Trader has made a final directional call after specialist analysis and adversarial debate. Your job is to evaluate risk and size the position.

RULES:
- Evaluate if the stop loss is placed at a logical level (beyond structure)
- Check risk:reward ratio — minimum 1.5:1, prefer 2:1+
- Size position based on ATR and account risk (max 2% account risk per trade)
- If event risk is HIGH (FOMC, CPI, NFP within 2 hours), reduce size by 50%
- If VIX is elevated (>25) or ATR is expanding rapidly, reduce size
- You may VETO the trade entirely if risk is unacceptable (signal becomes NO_TRADE)
- Provide max_hold_minutes based on timeframe and regime

Output: APPROVED/VETOED, position_size_pct, adjusted SL/TP if needed, max_hold_minutes, and risk assessment.""",
}


# ═══════════════════════════════════════════════════════════
#  AI SPECIALIST WRAPPER
# ═══════════════════════════════════════════════════════════

async def ask_specialist(role: str, prompt: str, max_tokens: int = 400, learning_context: str = "") -> str:
    """Query a specialist trader agent with their methodology-specific system prompt."""
    if not client:
        await asyncio.sleep(1)
        return f"[{role}] Mock response - missing API key."
    try:
        system_msg = SPECIALIST_PROMPTS.get(role, f"You are a hedge fund {role}. Provide decisive, data-driven analysis.")
        if learning_context:
            system_msg += f"\n\nHISTORICAL PERFORMANCE CONTEXT:\n{learning_context}"
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

    # Gate 3: Grade enforcement (defense-in-depth) — only F blocks trades
    if signal_grade == "F":
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
        mtf_data, market_context, econ_calendar, whale_alerts, cot_data = await asyncio.gather(
            loop.run_in_executor(executor, fetch_multi_timeframe_data, ticker, tf),
            loop.run_in_executor(executor, fetch_market_context),
            loop.run_in_executor(executor, get_economic_calendar),
            loop.run_in_executor(executor, whale_detector.analyze_ticker, ticker),
            loop.run_in_executor(executor, fetch_gold_cot),
        )

        # Session / Killzone detection (instant — no I/O)
        session_data = get_current_session()
        session_text = format_session_for_ai(session_data)

        # COT formatting
        cot_text = format_cot_for_ai(cot_data)

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

        # ── Asian Range (for London breakout levels) ──
        asian_range = {}
        if primary_df is not None and not primary_df.empty:
            asian_range = compute_asian_range(primary_df)

        # Stream ICT, Order Flow, and Backtest data to frontend panels
        yield emit("ICT", {"ticker": ticker, "timeframe": tf, "ict": ict_data})
        yield emit("ORDER_FLOW", order_flow_data)
        yield emit("MTF_ORDER_FLOW", mtf_of)
        yield emit("SESSION", session_data)

        # ── Intermarket Correlation Analysis ──
        # Run after we have a preliminary direction from scoring (two-pass)
        # First pass: get direction without intermarket modifier
        preliminary = calculate_enhanced_score(primary, ict_data, order_flow_data, mtf_confluence=mtf_of, session_data=session_data)
        prelim_dir = preliminary["direction"]

        # Now fetch intermarket with the preliminary direction
        correlation_data = await loop.run_in_executor(
            executor, analyze_intermarket, tf, prelim_dir
        )
        correlation_text = format_correlation_for_ai(correlation_data)
        yield emit("CORRELATION", correlation_data)

        # ── Calculate Enhanced Strategy Score (5-Factor Confluence) — FINAL with all modifiers ──
        enhanced = calculate_enhanced_score(
            primary, ict_data, order_flow_data,
            mtf_confluence=mtf_of,
            session_data=session_data,
            correlation_data=correlation_data,
        )
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

        # ── Load Obsidian agent performance if available ──
        obsidian_ctx = ""
        try:
            obsidian_path = os.path.join(os.path.expanduser("~"), "Documents", "Obsidian-Brain", "Trading-War-Room-Agent-Performance.md")
            if os.path.exists(obsidian_path):
                with open(obsidian_path, "r", encoding="utf-8") as f:
                    obsidian_ctx = f.read()[-2000:]  # last 2000 chars = most recent performance
        except Exception:
            pass

        combined_learning = learning_ctx
        if obsidian_ctx:
            combined_learning += f"\n\nAGENT PERFORMANCE HISTORY:\n{obsidian_ctx}"

        price_anchor = (
            f"\nCRITICAL: CURRENT LIVE PRICE of {ticker} is {current_price}. "
            f"ALL prices MUST be within realistic range of {current_price}. DO NOT hallucinate."
        )

        atr_val = primary.get("ATR_14", 0)

        # ── 1. SIX SPECIALIST TRADERS (parallel) ──
        specialist_prompts = {
            "ICT_TRADER": (
                f"Analyze {ticker} at {current_price} on {tf} using ICT/Smart Money methodology.\n\n"
                f"ICT DATA:\n{ict_text}\n\n"
                f"ORDER FLOW (for OB validation):\n{order_flow_text}\n\n"
                f"SESSION:\n{session_text}\n\n"
                f"SWING POINTS & STRUCTURE:\n{mtf_summary}\n"
                f"ATR(14): {atr_val}{price_anchor}"
            ),
            "ORDERFLOW_TRADER": (
                f"Analyze {ticker} at {current_price} on {tf} using Order Flow / Auction Market Theory.\n\n"
                f"ORDER FLOW DATA:\n{order_flow_text}\n\n"
                f"MTF ORDER FLOW:\n{mtf_of_text}\n\n"
                f"VOLUME PROFILE: POC={order_flow_data.get('summary', {}).get('poc', 'N/A')}, "
                f"VAH={order_flow_data.get('summary', {}).get('vah', 'N/A')}, "
                f"VAL={order_flow_data.get('summary', {}).get('val', 'N/A')}\n"
                f"VWAP Deviation: {order_flow_data.get('summary', {}).get('vwap_deviation', 0)} sigma\n"
                f"Divergences: {len(order_flow_data.get('divergences', []))}\n"
                f"Absorptions: {len(order_flow_data.get('absorptions', []))}\n"
                f"ATR(14): {atr_val}{price_anchor}"
            ),
            "SCALPER": (
                f"Analyze {ticker} at {current_price} on {tf} for momentum/scalp setups.\n\n"
                f"INDICATORS:\n{mtf_summary}\n\n"
                f"RSI(14): {primary.get('RSI_14', 'N/A')}\n"
                f"MACD histogram: {primary.get('MACD_histogram', 'N/A')}\n"
                f"BB upper: {primary.get('BB_upper', 'N/A')}, BB lower: {primary.get('BB_lower', 'N/A')}\n"
                f"StochRSI: {primary.get('StochRSI_K', 'N/A')}/{primary.get('StochRSI_D', 'N/A')}\n"
                f"EMA 9/21 cross: {primary.get('EMA_9_21_cross', 'N/A')}\n"
                f"ATR(14): {atr_val}, ADX: {primary.get('ADX', 'N/A')}\n"
                f"Price vs VWAP: {primary.get('price_vs_VWAP', 'N/A')}{price_anchor}"
            ),
            "MACRO_TRADER": (
                f"Analyze macro context for {ticker} at {current_price} on {tf}.\n\n"
                f"MARKET CONTEXT:\n{market_context}\n\n"
                f"ECONOMIC CALENDAR:\n{econ_calendar}\n\n"
                f"INTERMARKET CORRELATIONS:\n{correlation_text}\n\n"
                f"COT DATA:\n{cot_text}{price_anchor}"
            ),
            "STRUCTURE_TRADER": (
                f"Analyze price structure for {ticker} at {current_price} on {tf}.\n\n"
                f"MTF SUMMARY:\n{mtf_summary}\n\n"
                f"ICT STRUCTURE (swing points, BOS/CHoCH):\n{ict_text}\n\n"
                f"EMA 9: {primary.get('EMA_9', 'N/A')}, EMA 21: {primary.get('EMA_21', 'N/A')}, "
                f"EMA 50: {primary.get('EMA_50', 'N/A')}\n"
                f"ATR(14): {atr_val}, ADX: {primary.get('ADX', 'N/A')}{price_anchor}"
            ),
            "WHALE_TRACKER": (
                f"Analyze institutional flow for {ticker} at {current_price} on {tf}.\n\n"
                f"WHALE ALERTS:\n{whale_text if whale_text else 'No whale alerts detected'}\n\n"
                f"ORDER FLOW (absorption/imbalances):\n{order_flow_text}\n\n"
                f"COT DATA:\n{cot_text}\n\n"
                f"Volume ratio: {primary.get('volume_ratio', 'N/A')}x average{price_anchor}"
            ),
        }

        # Run all 6 specialists in parallel
        specialist_keys = list(specialist_prompts.keys())
        specialist_tasks = [
            ask_specialist(role, prompt, max_tokens=400, learning_context=combined_learning)
            for role, prompt in specialist_prompts.items()
        ]
        specialist_results_list = await asyncio.gather(*specialist_tasks)

        specialist_outputs = {}
        specialist_votes = {}
        for i, role in enumerate(specialist_keys):
            text = specialist_results_list[i]
            specialist_outputs[role] = text
            yield emit(role, {"text": text})
            # Parse direction and confidence from output for vote tracking
            _dir = "NO_TRADE"
            _conf = 50
            upper = text.upper()
            if "DIRECTION: LONG" in upper or "DIRECTION (LONG" in upper or "\nLONG\n" in upper or "FINAL_DIRECTION: LONG" in upper:
                _dir = "LONG"
            elif "DIRECTION: SHORT" in upper or "DIRECTION (SHORT" in upper or "\nSHORT\n" in upper or "FINAL_DIRECTION: SHORT" in upper:
                _dir = "SHORT"
            import re as _re
            conf_match = _re.search(r'CONFIDENCE[:\s]*(\d+)', upper)
            if conf_match:
                _conf = int(conf_match.group(1))
            specialist_votes[role] = {"direction": _dir, "confidence": _conf}

        # ── 2. HEAD TRADER — Initial Synthesis ──
        specialist_summary = "\n\n".join([
            f"=== {role} ===\n{text}" for role, text in specialist_outputs.items()
        ])

        head_trader_prompt = (
            f"You have 6 specialist traders who analyzed {ticker} at {current_price} on {tf}.\n\n"
            f"SPECIALIST ANALYSES:\n{specialist_summary}\n\n"
            f"ENHANCED SCORING:\n"
            f"- Strategy Direction: {strat_dir}\n"
            f"- Strategy Score: {strat_score} (-100 to +100)\n"
            f"- Signal Grade: {signal_grade}\n"
            f"- Market Regime: {market_regime}\n"
            f"- Factors Aligned: {factors_aligned}/5\n"
            f"- Order Flow Agrees: {order_flow_agrees}\n\n"
            f"SPECIALIST VOTES: {json.dumps(specialist_votes)}\n\n"
            f"ATR(14): {atr_val}{price_anchor}\n\n"
            f"Synthesize all specialist views and make your INITIAL trade decision."
        )

        head_trader_text = await ask_specialist("HEAD_TRADER", head_trader_prompt, max_tokens=500, learning_context=combined_learning)
        yield emit("HEAD_TRADER", {"text": head_trader_text})

        # ── 3. DEVIL'S ADVOCATE DEBATE (parallel) ──
        debate_context = (
            f"HEAD TRADER'S INITIAL CALL:\n{head_trader_text}\n\n"
            f"SPECIALIST ANALYSES:\n{specialist_summary}\n\n"
            f"Market: {ticker} at {current_price}, Regime: {market_regime}, Grade: {signal_grade}"
        )

        bull_task = ask_specialist("BULL_ADVOCATE",
            f"The Head Trader just made this call on {ticker}:\n\n{debate_context}\n\n"
            f"Make the STRONGEST possible BULLISH case.{price_anchor}",
            max_tokens=350, learning_context=combined_learning)

        bear_task = ask_specialist("BEAR_ADVOCATE",
            f"The Head Trader just made this call on {ticker}:\n\n{debate_context}\n\n"
            f"Make the STRONGEST possible BEARISH / cautious case.{price_anchor}",
            max_tokens=350, learning_context=combined_learning)

        bull_text, bear_text = await asyncio.gather(bull_task, bear_task)
        yield emit("BULL_ADVOCATE", {"text": bull_text})
        yield emit("BEAR_ADVOCATE", {"text": bear_text})

        # ── 4. HEAD TRADER FINAL — Post-Debate Decision ──
        final_prompt = (
            f"You made this INITIAL call on {ticker} at {current_price}:\n{head_trader_text}\n\n"
            f"BULL ADVOCATE argued:\n{bull_text}\n\n"
            f"BEAR ADVOCATE argued:\n{bear_text}\n\n"
            f"SPECIALIST VOTES: {json.dumps(specialist_votes)}\n"
            f"Strategy Direction: {strat_dir}, Score: {strat_score}, Grade: {signal_grade}\n"
            f"ATR(14): {atr_val}{price_anchor}\n\n"
            f"Make your FINAL decision. You may CONFIRM, REVERSE, or DOWNGRADE to NO_TRADE."
        )

        head_final_text = await ask_specialist("HEAD_TRADER_FINAL", final_prompt, max_tokens=500, learning_context=combined_learning)
        yield emit("HEAD_TRADER_FINAL", {"text": head_final_text})

        # ── 5. RISK MANAGER ──
        risk_text = await ask_specialist("RISK_MANAGER",
            f"The Head Trader's FINAL decision on {ticker} at {current_price} ({tf}):\n{head_final_text}\n\n"
            f"ATR(14): {atr_val}. Risk profile: {risk}.\n"
            f"Market regime: {market_regime}. Signal grade: {signal_grade}.\n"
            f"Event risk from MACRO_TRADER: {specialist_outputs.get('MACRO_TRADER', 'N/A')[:200]}\n"
            f"{market_context}\n\n"
            f"Approve or veto? Size recommendation.",
            max_tokens=300, learning_context=combined_learning)
        yield emit("RISK_MANAGER", {"text": risk_text})

        # ── 6. SIGNAL ENGINE ──
        atr_num = float(atr_val) if atr_val and atr_val != "N/A" else (float(current_price) * 0.005 if isinstance(current_price, (int, float)) else 50)

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

HEAD TRADER FINAL DECISION:
{head_final_text[:600]}

RISK MANAGER ASSESSMENT:
{risk_text[:400]}

SPECIALIST AGREEMENT: {json.dumps(specialist_votes)}

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
- YOUR SIGNAL MUST MATCH THE HEAD TRADER'S FINAL DIRECTION. If Head Trader said NO_TRADE, output NO_TRADE.
- IF SIGNAL GRADE IS 'F', USE 'NO_TRADE'. Grade C may still produce cautious trades.
- IF THE RISK MANAGER VETOED, USE 'NO_TRADE'.
- IF THE RISK IS TOO HIGH OR CONTEXT IS BAD, YOU MAY DOWNGRADE TO 'NO_TRADE'.
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
        signal_text = await ask_specialist("SIGNAL_ENGINE", json_prompt, max_tokens=1200, learning_context=combined_learning)
        clean_json = signal_text.replace("```json", "").replace("```", "").strip()

        # Try to extract JSON object if model added surrounding text
        if not clean_json.startswith("{"):
            import re
            match = re.search(r'\{[\s\S]*\}', clean_json)
            if match:
                clean_json = match.group(0)

        # Fix common LLM JSON issues
        clean_json = clean_json.replace("True", "true").replace("False", "false").replace("None", "null")
        # Remove trailing commas before } or ]
        import re
        clean_json = re.sub(r',\s*([}\]])', r'\1', clean_json)

        try:
            signal_data = json.loads(clean_json)
        except json.JSONDecodeError as e:
            print(f"SIGNAL_ENGINE JSON parse failed: {e}\nRaw (first 500): {signal_text[:500]}")
            print(f"Cleaned (first 500): {clean_json[:500]}")
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

        # Inject ICT features for ML training
        signal_data["liquidity_grabs"] = ict_data.get("liquidity_grabs", [])
        signal_data["swing_failure_patterns"] = ict_data.get("swing_failure_patterns", [])
        signal_data["judas_swing"] = ict_data.get("judas_swing")

        # Inject specialist votes + debate data for self-learning
        signal_data["specialist_votes"] = specialist_votes
        signal_data["head_trader_initial"] = head_trader_text[:500]
        signal_data["bull_advocate"] = bull_text[:500]
        signal_data["bear_advocate"] = bear_text[:500]
        signal_data["head_trader_final"] = head_final_text[:500]

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

        # ── Full feature snapshot for ML training ──
        signal_data["score"] = enhanced.get("score", 0)
        signal_data["factor_scores"] = enhanced.get("factor_scores", {})
        signal_data["session_modifier"] = enhanced.get("session_modifier", 1.0)
        signal_data["session_label"] = enhanced.get("session_label", "ACTIVE")
        signal_data["correlation_modifier"] = enhanced.get("correlation_modifier", 1.0)
        signal_data["correlation_label"] = enhanced.get("correlation_label", "")
        # Full raw indicator snapshot (replaces sparse indicators_used for ML)
        _scalar_keys = (int, float, str, bool, type(None))
        signal_data["raw_indicators"] = {
            k: v for k, v in primary.items()
            if isinstance(v, _scalar_keys) and k != "computation_error"
        }

        # ── ML Signal Filter ──
        # Once enough outcomes exist the model runs live; before that it's transparent (0.5)
        ml_prob = predict_win_probability(signal_data)
        signal_data["ml_win_probability"] = ml_prob
        if is_model_ready() and signal_data.get("signal") in ("LONG", "SHORT"):
            if ml_prob < WIN_PROBABILITY_THRESHOLD:
                signal_data["signal"] = "NO_TRADE"
                signal_data["reasons"] = signal_data.get("reasons", []) + [
                    f"ML filter blocked: P(WIN)={ml_prob:.2f} < {WIN_PROBABILITY_THRESHOLD} threshold"
                ]

        # Store signal in history and send Telegram alert
        await store_signal(signal_data)
        await send_telegram_alert(signal_data)

        yield emit("SIGNAL_ENGINE", signal_data)

    except Exception as e:
        yield emit("ERROR", {"text": f"Backend stream failed: {str(e)}"})


# ═══════════════════════════════════════════════════════════
#  SELF-LEARNING: OBSIDIAN AGENT PERFORMANCE MEMORY
# ═══════════════════════════════════════════════════════════

def _update_obsidian_agent_performance():
    """Compute per-specialist accuracy from resolved signals and write to Obsidian vault."""
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        signals_raw = conn.execute(
            "SELECT data FROM signals WHERE resolved = 1 ORDER BY id DESC LIMIT 200"
        ).fetchall()
        outcomes_raw = conn.execute(
            "SELECT data FROM outcomes ORDER BY id DESC LIMIT 200"
        ).fetchall()
        conn.close()

        if len(signals_raw) < 5 or len(outcomes_raw) < 5:
            return  # Not enough data yet

        signals = [json.loads(r[0]) for r in signals_raw]
        outcomes = [json.loads(r[0]) for r in outcomes_raw]

        # Track per-agent accuracy
        agent_stats = {}
        specialist_names = ["ICT_TRADER", "ORDERFLOW_TRADER", "SCALPER", "MACRO_TRADER", "STRUCTURE_TRADER", "WHALE_TRACKER"]

        for i in range(min(len(signals), len(outcomes))):
            sig = signals[i]
            out = outcomes[i]
            votes = sig.get("specialist_votes", {})
            final_dir = sig.get("signal", "NO_TRADE")
            result = out.get("result", "")

            if final_dir == "NO_TRADE" or result not in ("WIN", "LOSS"):
                continue

            for agent_name in specialist_names:
                if agent_name not in votes:
                    continue
                if agent_name not in agent_stats:
                    agent_stats[agent_name] = {"agreed": 0, "wins_when_agreed": 0, "total": 0}

                agent_stats[agent_name]["total"] += 1
                if votes[agent_name].get("direction") == final_dir:
                    agent_stats[agent_name]["agreed"] += 1
                    if result == "WIN":
                        agent_stats[agent_name]["wins_when_agreed"] += 1

        if not agent_stats:
            return

        # Build markdown table
        lines = [
            f"## Agent Performance — Updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "| Agent | Signals Agreed | Win Rate When Agreed | Reliability |",
            "|-------|---------------|---------------------|-------------|",
        ]

        for agent in specialist_names:
            stats = agent_stats.get(agent, {"agreed": 0, "wins_when_agreed": 0, "total": 0})
            agreed = stats["agreed"]
            wr = round(stats["wins_when_agreed"] / max(agreed, 1) * 100, 1)
            reliability = "HIGH" if wr >= 50 else "MEDIUM" if wr >= 40 else "LOW"
            lines.append(f"| {agent} | {agreed}/{stats['total']} | {wr}% | {reliability} |")

        lines.append("")
        lines.append(f"Total resolved signals analyzed: {min(len(signals), len(outcomes))}")

        obsidian_dir = os.path.join(os.path.expanduser("~"), "Documents", "Obsidian-Brain")
        os.makedirs(obsidian_dir, exist_ok=True)
        obsidian_path = os.path.join(obsidian_dir, "Trading-War-Room-Agent-Performance.md")

        with open(obsidian_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    except Exception as e:
        print(f"Obsidian agent performance update failed: {e}")


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
                "footprint": of_data.get("footprint", []),
                "heatmap": of_data.get("heatmap", []),
                "liquidity_heatmap": of_data.get("liquidity_heatmap", []),
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
        # Use actual futures symbols — correct prices, full session coverage
        # (10-15 min delay on free yfinance feeds, but prices match signal levels)
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
                "footprint": of_data.get("footprint", []),
                "heatmap": of_data.get("heatmap", []),
                "liquidity_heatmap": of_data.get("liquidity_heatmap", []),
                "summary": of_data.get("summary", {}),
            } if of_data else {},
            "ticker": ticker,
            "symbol": yf_symbol,
            "chart_source": yf_symbol,
            "timeframe": request.timeframe,
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
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
#  WEBSOCKET LIVE PRICE FEED
# ═══════════════════════════════════════════════════════════

@app.websocket("/ws/prices/{ticker}")
async def ws_prices(websocket: WebSocket, ticker: str):
    """Stream live candle updates for a ticker via WebSocket."""
    await websocket.accept()
    symbol = ticker.upper().strip()
    q = price_feed.subscribe(symbol)
    try:
        while True:
            msg = await q.get()
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        price_feed.unsubscribe(symbol, q)


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
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-haiku",
    "google/gemini-2.5-flash",
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

5-Factor Confluence Score: {scan.get('score', 0)}/100
Strategy Direction: {scan.get('direction', 'NEUTRAL')}
Signal Grade: {scan.get('grade', 'N/A')}
Market Regime: {scan.get('regime', 'N/A')}
Order Flow Bias: {scan.get('order_flow_bias', 'NEUTRAL')}

IMPORTANT: The 5-factor confluence system has already scored this setup.
If signal grade is F, you should vote NO_TRADE. Grade C can still produce cautious trades.
Your vote should be consistent with the strategy direction and grade above.

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
        "regime": scan.get("regime", "N/A"),
        "signal_grade": scan.get("grade", "N/A"),
        "strategy_score": scan.get("score", 0),
        "strategy_direction": scan.get("direction", "NEUTRAL"),
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

@app.post("/api/v1/seed-backtest")
async def seed_backtest_endpoint(request: SeedBacktestRequest):
    """
    Import historical CSV data and seed the SQLite DB with signal+outcome pairs
    to bootstrap the XGBoost ML signal filter.

    The seeder runs in a thread pool executor so it does not block the event loop.
    For large files (1yr of 1m bars ≈ 130k rows) expect ~2-3 minutes runtime.
    """
    from fastapi import HTTPException
    from csv_backtest_seeder import seed_from_csv

    if not os.path.exists(request.csv_path):
        raise HTTPException(status_code=400, detail=f"File not found: {request.csv_path}")

    if request.min_grade not in ("A+", "A", "B", "C", "F"):
        raise HTTPException(status_code=400, detail="min_grade must be one of: A+, A, B, C, F")

    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(
        executor,
        lambda: seed_from_csv(
            filepath=request.csv_path,
            ticker=request.ticker,
            min_grade=request.min_grade,
            max_bars=request.max_bars,
        ),
    )
    return {
        "status": "completed",
        "stats": stats,
        "ml_model_ready": is_model_ready(),
    }

@app.post("/api/v1/outcomes/report")
async def report_outcome_endpoint(report: OutcomeReport):
    result = report_outcome(report.dict())
    # Trigger ML retraining in background whenever a new outcome is recorded
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, auto_train_if_ready, DB_PATH)
    # Update Obsidian agent performance memory in background
    loop.run_in_executor(executor, _update_obsidian_agent_performance)
    return result

@app.get("/api/v1/outcomes")
async def get_outcomes_endpoint():
    return get_outcomes()

@app.get("/api/v1/ml-stats")
async def ml_stats_endpoint():
    """Return ML model training status and feature importances."""
    return get_model_stats()


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
#  MARKET OVERVIEW / HEATMAP
# ═══════════════════════════════════════════════════════════

HEATMAP_TICKERS = {
    "Indices": ["NQ1", "ES1", "YM1", "RTY1"],
    "Energy": ["CL1"],
    "Metals": ["GC1", "SI1"],
    "Bonds": ["ZB1"],
    "Crypto": ["BTC1", "ETH1"],
}

_market_cache: dict = {"data": None, "ts": 0}


def _fetch_ticker_snapshot(ticker: str) -> dict:
    """Fetch current price and % change for a single ticker."""
    try:
        yf_symbol = resolve_ticker(ticker)
        tk = yf.Ticker(yf_symbol)
        info = tk.fast_info
        price = round(float(info.last_price), 2) if hasattr(info, "last_price") else 0
        prev = round(float(info.previous_close), 2) if hasattr(info, "previous_close") else 0
        pct = round((price - prev) / prev * 100, 2) if prev > 0 else 0
        return {"ticker": ticker, "price": price, "change_pct": pct}
    except Exception:
        return {"ticker": ticker, "price": 0, "change_pct": 0}


@app.get("/api/v1/market-overview")
async def market_overview():
    """Return grouped market data for heatmap. Cached 30s."""
    import time as _time

    now = _time.time()
    if _market_cache["data"] and now - _market_cache["ts"] < 30:
        return _market_cache["data"]

    result = {}
    all_tickers = [t for group in HEATMAP_TICKERS.values() for t in group]
    snapshots = await asyncio.gather(
        *[asyncio.to_thread(_fetch_ticker_snapshot, t) for t in all_tickers]
    )
    snap_map = {s["ticker"]: s for s in snapshots}

    for group, tickers in HEATMAP_TICKERS.items():
        result[group] = [snap_map.get(t, {"ticker": t, "price": 0, "change_pct": 0}) for t in tickers]

    _market_cache["data"] = result
    _market_cache["ts"] = now
    return result


# ═══════════════════════════════════════════════════════════
#  ALERTS API + AUTO-SCANNER
# ═══════════════════════════════════════════════════════════

SCAN_WATCHLIST = ["NQ1", "ES1", "YM1", "RTY1", "GC1", "CL1", "BTC1"]

@app.get("/api/v1/alerts")
async def alerts_endpoint(since: str | None = None, limit: int = 30):
    """Return recent alerts, optionally filtered by since timestamp."""
    alerts = get_alerts(since=since, limit=limit)
    unread = get_unread_count()
    return {"alerts": alerts, "unread": unread}

@app.post("/api/v1/alerts/read")
async def mark_read_endpoint():
    """Mark all alerts as read."""
    mark_alerts_read()
    return {"status": "ok"}


async def auto_scan_loop():
    """Background task: scan watchlist every 5 minutes for high-grade signals."""
    await asyncio.sleep(30)  # Wait for app to stabilize

    while True:
        try:
            for ticker in SCAN_WATCHLIST:
                try:
                    result = await asyncio.to_thread(quick_scan_ticker, ticker, "5m")
                    if not result or result.get("error"):
                        continue

                    grade = result.get("grade", "F")
                    score = result.get("score", 0)
                    direction = result.get("direction", "NEUTRAL")

                    # Only alert on grade B+ or better with clear direction
                    if grade in ("A+", "A", "A-", "B+") and direction in ("LONG", "SHORT") and score >= 60:
                        store_alert(
                            alert_type="signal_opportunity",
                            ticker=ticker,
                            data={
                                "grade": grade,
                                "score": score,
                                "direction": direction,
                                "price": result.get("current_price"),
                                "rsi": result.get("rsi"),
                                "vol_ratio": result.get("vol_ratio"),
                                "message": f"{ticker} {direction} — Grade {grade} ({score}%)",
                            },
                        )
                except Exception:
                    pass

                await asyncio.sleep(2)  # Brief pause between tickers

        except Exception as e:
            print(f"Auto-scan error: {e}")

        await asyncio.sleep(300)  # 5 minutes


# ═══════════════════════════════════════════════════════════
#  STARTUP & HEALTH
# ═══════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application launch."""
    asyncio.create_task(monitor_active_trades(executor, resolve_ticker))
    asyncio.create_task(auto_scan_loop())


# ═══════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS
# ═══════════════════════════════════════════════════════════

ADMIN_KEY = os.getenv("ADMIN_KEY", "warroom-admin-2026")

def _check_admin(key: str):
    from fastapi import HTTPException
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@app.get("/api/v1/admin/dashboard")
async def admin_dashboard(key: str = ""):
    """Full admin overview: DB stats, ML model, signal quality, recent performance."""
    _check_admin(key)
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    total_signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    resolved_signals = conn.execute("SELECT COUNT(*) FROM signals WHERE resolved = 1").fetchone()[0]
    total_outcomes = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]

    # Win rate from outcomes
    wins = 0
    losses = 0
    if total_outcomes > 0:
        rows = conn.execute("SELECT data FROM outcomes").fetchall()
        for r in rows:
            o = json.loads(r[0])
            if o.get("result") == "WIN":
                wins += 1
            else:
                losses += 1

    # Grade distribution from signals
    grade_dist = {"A+": 0, "A": 0, "B": 0, "C": 0, "other": 0}
    if resolved_signals > 0:
        sig_rows = conn.execute("SELECT data FROM signals WHERE resolved = 1 ORDER BY id DESC LIMIT 10000").fetchall()
        for r in sig_rows:
            s = json.loads(r[0])
            g = s.get("signal_grade", "other")
            if g in grade_dist:
                grade_dist[g] += 1
            else:
                grade_dist["other"] += 1

    # Recent signals (last 20)
    recent_rows = conn.execute("SELECT data FROM signals ORDER BY id DESC LIMIT 20").fetchall()
    recent_signals = []
    for r in recent_rows:
        s = json.loads(r[0])
        recent_signals.append({
            "ticker": s.get("ticker"),
            "signal": s.get("signal"),
            "grade": s.get("signal_grade"),
            "score": s.get("score"),
            "confidence": s.get("confidence"),
            "timestamp": s.get("timestamp"),
        })

    conn.close()

    ml_stats = get_model_stats()

    return {
        "db": {
            "total_signals": total_signals,
            "resolved_signals": resolved_signals,
            "total_outcomes": total_outcomes,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / max(total_outcomes, 1) * 100, 1),
        },
        "grade_distribution": grade_dist,
        "ml": ml_stats,
        "ml_threshold": WIN_PROBABILITY_THRESHOLD,
        "recent_signals": recent_signals,
    }


@app.post("/api/v1/admin/retrain")
async def admin_retrain(key: str = ""):
    """Force retrain the ML model on all available data."""
    _check_admin(key)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, train_model, DB_PATH)
    return {"status": "retrained", "result": result}


@app.post("/api/v1/admin/clear-db")
async def admin_clear_db(key: str = "", table: str = ""):
    """Clear signals and/or outcomes tables. Use with caution."""
    _check_admin(key)
    from fastapi import HTTPException
    import sqlite3

    if table not in ("signals", "outcomes", "all"):
        raise HTTPException(status_code=400, detail="table must be 'signals', 'outcomes', or 'all'")

    conn = sqlite3.connect(DB_PATH)
    if table in ("signals", "all"):
        conn.execute("DELETE FROM signals")
    if table in ("outcomes", "all"):
        conn.execute("DELETE FROM outcomes")
    conn.commit()
    conn.close()

    return {"status": "cleared", "table": table}


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "war-room-ai", "version": "6.0-order-flow"}
