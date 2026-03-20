import os
import json
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

import openai
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

load_dotenv()

app = FastAPI(title="AI Trading War Room Backend")
executor = ThreadPoolExecutor(max_workers=4)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Clients ───────────────────────────────────────────────
KILO_API_KEY = os.getenv("KILO_API_KEY", "")

try:
    client = openai.AsyncOpenAI(
        api_key=KILO_API_KEY,
        base_url="https://api.kilo.ai/api/gateway"
    )
except Exception as e:
    print(f"Warning: OpenAI client init failed: {e}")
    client = None

# ─── Ticker Mapping ────────────────────────────────────────
TICKER_MAP = {
    "NQ1": "NQ=F", "NQ": "NQ=F", "NASDAQ": "NQ=F",
    "ES1": "ES=F", "ES": "ES=F", "SPX": "ES=F",
    "YM1": "YM=F", "YM": "YM=F", "DOW": "YM=F",
    "RTY1": "RTY=F", "RTY": "RTY=F",
    "CL1": "CL=F", "CL": "CL=F", "OIL": "CL=F",
    "GC1": "GC=F", "GC": "GC=F", "GOLD": "GC=F", "XAUUSD": "GC=F",
    "SI1": "SI=F", "SI": "SI=F", "SILVER": "SI=F",
    "ZB1": "ZB=F", "ZB": "ZB=F",
    "BTCUSD": "BTC-USD", "BTC": "BTC-USD",
    "ETHUSD": "ETH-USD", "ETH": "ETH-USD",
    "DXY": "DX-Y.NYB",
}

# Market context tickers (always fetched)
CONTEXT_TICKERS = {
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "SP500": "ES=F",
}

# ─── Models ────────────────────────────────────────────────
class AnalysisRequest(BaseModel):
    ticker: str
    timeframe: str
    riskProfile: str


def resolve_ticker(raw: str) -> str:
    return TICKER_MAP.get(raw.upper().strip(), raw.upper().strip())


# ═══════════════════════════════════════════════════════════
#  1. SERVER-SIDE TECHNICAL INDICATORS
# ═══════════════════════════════════════════════════════════

def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute real technical indicators from OHLCV data using pandas-ta."""
    if df.empty or len(df) < 20:
        return {"error": "Insufficient data for indicator computation"}

    indicators = {}

    try:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # RSI
        rsi = ta.rsi(close, length=14)
        if rsi is not None and len(rsi) > 0:
            indicators["RSI_14"] = round(float(rsi.iloc[-1]), 2) if not pd.isna(rsi.iloc[-1]) else None

        # MACD
        macd = ta.macd(close, fast=12, slow=26, signal=9)
        if macd is not None and not macd.empty:
            indicators["MACD_line"] = round(float(macd.iloc[-1, 0]), 2) if not pd.isna(macd.iloc[-1, 0]) else None
            indicators["MACD_histogram"] = round(float(macd.iloc[-1, 1]), 2) if not pd.isna(macd.iloc[-1, 1]) else None
            indicators["MACD_signal"] = round(float(macd.iloc[-1, 2]), 2) if not pd.isna(macd.iloc[-1, 2]) else None

        # Bollinger Bands
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None and not bb.empty:
            indicators["BB_upper"] = round(float(bb.iloc[-1, 0]), 2) if not pd.isna(bb.iloc[-1, 0]) else None
            indicators["BB_mid"] = round(float(bb.iloc[-1, 1]), 2) if not pd.isna(bb.iloc[-1, 1]) else None
            indicators["BB_lower"] = round(float(bb.iloc[-1, 2]), 2) if not pd.isna(bb.iloc[-1, 2]) else None

        # ATR
        atr = ta.atr(high, low, close, length=14)
        if atr is not None and len(atr) > 0:
            indicators["ATR_14"] = round(float(atr.iloc[-1]), 2) if not pd.isna(atr.iloc[-1]) else None

        # EMAs
        for period in [9, 21, 50, 200]:
            ema = ta.ema(close, length=period)
            if ema is not None and len(ema) > 0 and not pd.isna(ema.iloc[-1]):
                indicators[f"EMA_{period}"] = round(float(ema.iloc[-1]), 2)

        # VWAP (intraday only - needs volume)
        try:
            vwap = ta.vwap(high, low, close, volume)
            if vwap is not None and len(vwap) > 0 and not pd.isna(vwap.iloc[-1]):
                indicators["VWAP"] = round(float(vwap.iloc[-1]), 2)
        except Exception:
            pass

        # Stochastic RSI
        stochrsi = ta.stochrsi(close, length=14)
        if stochrsi is not None and not stochrsi.empty:
            indicators["StochRSI_K"] = round(float(stochrsi.iloc[-1, 0]), 2) if not pd.isna(stochrsi.iloc[-1, 0]) else None
            indicators["StochRSI_D"] = round(float(stochrsi.iloc[-1, 1]), 2) if not pd.isna(stochrsi.iloc[-1, 1]) else None

        # ADX (trend strength)
        adx = ta.adx(high, low, close, length=14)
        if adx is not None and not adx.empty:
            indicators["ADX"] = round(float(adx.iloc[-1, 0]), 2) if not pd.isna(adx.iloc[-1, 0]) else None

        # Volume analysis
        avg_vol = volume.rolling(20).mean()
        if avg_vol is not None and len(avg_vol) > 0 and not pd.isna(avg_vol.iloc[-1]):
            current_vol = float(volume.iloc[-1])
            average_vol = float(avg_vol.iloc[-1])
            indicators["current_volume"] = int(current_vol)
            indicators["avg_volume_20"] = int(average_vol)
            indicators["volume_ratio"] = round(current_vol / average_vol, 2) if average_vol > 0 else 0

        # Price position relative to key levels
        current_price = float(close.iloc[-1])
        indicators["current_price"] = round(current_price, 2)

        if "EMA_9" in indicators and "EMA_21" in indicators:
            indicators["EMA_9_21_cross"] = "BULLISH" if indicators["EMA_9"] > indicators["EMA_21"] else "BEARISH"

        if "VWAP" in indicators:
            indicators["price_vs_VWAP"] = "ABOVE" if current_price > indicators["VWAP"] else "BELOW"

        if indicators.get("RSI_14"):
            rsi_val = indicators["RSI_14"]
            if rsi_val > 70:
                indicators["RSI_condition"] = "OVERBOUGHT"
            elif rsi_val < 30:
                indicators["RSI_condition"] = "OVERSOLD"
            else:
                indicators["RSI_condition"] = "NEUTRAL"

    except Exception as e:
        indicators["computation_error"] = str(e)

    return indicators


def format_indicators_for_ai(indicators: dict, timeframe_label: str) -> str:
    """Format computed indicators into a readable string for AI prompts."""
    if "error" in indicators:
        return f"[{timeframe_label}] {indicators['error']}"

    lines = [f"═══ {timeframe_label} INDICATORS ═══"]

    price = indicators.get("current_price", "N/A")
    lines.append(f"  Price: {price}")

    # Trend
    ema_cross = indicators.get("EMA_9_21_cross", "N/A")
    adx = indicators.get("ADX", "N/A")
    lines.append(f"  Trend: EMA 9/21 cross={ema_cross}, ADX={adx}")

    emas = []
    for p in [9, 21, 50, 200]:
        v = indicators.get(f"EMA_{p}")
        if v:
            emas.append(f"EMA{p}={v}")
    if emas:
        lines.append(f"  EMAs: {', '.join(emas)}")

    # Momentum
    rsi = indicators.get("RSI_14", "N/A")
    rsi_cond = indicators.get("RSI_condition", "")
    lines.append(f"  RSI(14): {rsi} ({rsi_cond})")

    macd_h = indicators.get("MACD_histogram", "N/A")
    macd_l = indicators.get("MACD_line", "N/A")
    macd_s = indicators.get("MACD_signal", "N/A")
    lines.append(f"  MACD: line={macd_l}, signal={macd_s}, histogram={macd_h}")

    stoch_k = indicators.get("StochRSI_K", "N/A")
    stoch_d = indicators.get("StochRSI_D", "N/A")
    lines.append(f"  StochRSI: K={stoch_k}, D={stoch_d}")

    # Volatility
    atr = indicators.get("ATR_14", "N/A")
    bb_u = indicators.get("BB_upper", "N/A")
    bb_m = indicators.get("BB_mid", "N/A")
    bb_l = indicators.get("BB_lower", "N/A")
    lines.append(f"  ATR(14): {atr}")
    lines.append(f"  Bollinger: upper={bb_u}, mid={bb_m}, lower={bb_l}")

    # Volume
    vwap = indicators.get("VWAP", "N/A")
    vol_ratio = indicators.get("volume_ratio", "N/A")
    price_vs_vwap = indicators.get("price_vs_VWAP", "N/A")
    lines.append(f"  VWAP: {vwap} (price {price_vs_vwap})")
    lines.append(f"  Volume ratio (vs 20-avg): {vol_ratio}x")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  2. MULTI-TIMEFRAME ANALYSIS
# ═══════════════════════════════════════════════════════════

TIMEFRAME_CONFIG = {
    "1m": [("1m", "1d", "1-Min"), ("5m", "5d", "5-Min"), ("15m", "5d", "15-Min"), ("1h", "30d", "1-Hour")],
    "2m": [("2m", "5d", "2-Min"), ("5m", "5d", "5-Min"), ("15m", "5d", "15-Min"), ("1h", "30d", "1-Hour")],
    "5m": [("5m", "5d", "5-Min"), ("15m", "5d", "15-Min"), ("1h", "30d", "1-Hour"), ("1d", "60d", "Daily")],
    "15m": [("5m", "5d", "5-Min"), ("15m", "5d", "15-Min"), ("1h", "30d", "1-Hour"), ("1d", "60d", "Daily")],
    "1h": [("15m", "5d", "15-Min"), ("1h", "30d", "1-Hour"), ("1d", "60d", "Daily")],
    "4h": [("1h", "30d", "1-Hour"), ("1d", "90d", "Daily")],
}


def fetch_multi_timeframe_data(ticker: str, primary_tf: str) -> dict:
    """Fetch OHLCV data and compute indicators across multiple timeframes."""
    yf_symbol = resolve_ticker(ticker)
    configs = TIMEFRAME_CONFIG.get(primary_tf, TIMEFRAME_CONFIG["5m"])

    results = {}
    bars_data = None  # Store primary TF bars for the signal engine

    for interval, period, label in configs:
        try:
            tk = yf.Ticker(yf_symbol)
            df = tk.history(period=period, interval=interval)

            if df.empty:
                results[label] = {"error": f"No data for {interval}"}
                continue

            indicators = compute_indicators(df)
            results[label] = indicators

            # Store the primary timeframe bars for raw data context
            if interval == primary_tf or (bars_data is None):
                recent = df.tail(10)
                bars = []
                for idx, row in recent.iterrows():
                    bars.append({
                        "time": str(idx),
                        "O": round(float(row["Open"]), 2),
                        "H": round(float(row["High"]), 2),
                        "L": round(float(row["Low"]), 2),
                        "C": round(float(row["Close"]), 2),
                        "V": int(row["Volume"])
                    })
                bars_data = bars

        except Exception as e:
            results[label] = {"error": str(e)}

    return {"indicators": results, "bars": bars_data or [], "symbol": yf_symbol}


def build_mtf_summary(mtf_data: dict, ticker: str) -> str:
    """Build a human-readable multi-timeframe summary for AI prompts."""
    lines = [f"╔══════════════════════════════════════╗"]
    lines.append(f"║  MULTI-TIMEFRAME ANALYSIS: {ticker}")
    lines.append(f"╚══════════════════════════════════════╝\n")

    for label, indicators in mtf_data["indicators"].items():
        lines.append(format_indicators_for_ai(indicators, label))
        lines.append("")

    # MTF Confluence summary
    trends = []
    for label, ind in mtf_data["indicators"].items():
        if isinstance(ind, dict) and "EMA_9_21_cross" in ind:
            trends.append(f"{label}: {ind['EMA_9_21_cross']}")

    if trends:
        lines.append(f"═══ MTF TREND CONFLUENCE ═══")
        for t in trends:
            lines.append(f"  {t}")

        bullish_count = sum(1 for t in trends if "BULLISH" in t)
        bearish_count = sum(1 for t in trends if "BEARISH" in t)
        lines.append(f"  Alignment: {bullish_count} BULLISH / {bearish_count} BEARISH out of {len(trends)} timeframes")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  3. MARKET CONTEXT LAYER (VIX, DXY, US10Y, ES)
# ═══════════════════════════════════════════════════════════

def fetch_market_context() -> str:
    """Fetch real-time market context from correlated instruments."""
    lines = ["═══ MARKET CONTEXT ═══"]

    for name, symbol in CONTEXT_TICKERS.items():
        try:
            tk = yf.Ticker(symbol)
            df = tk.history(period="2d", interval="5m")
            if df.empty:
                lines.append(f"  {name}: No data")
                continue

            current = round(float(df["Close"].iloc[-1]), 2)

            # Calculate session change
            day_df = tk.history(period="1d", interval="1d")
            if not day_df.empty and len(day_df) >= 1:
                prev_close = float(day_df["Close"].iloc[-1])
                pct = round(((current - prev_close) / prev_close) * 100, 2)
            else:
                pct = 0.0

            direction = "▲" if pct > 0 else "▼" if pct < 0 else "─"
            lines.append(f"  {name}: {current} ({direction} {pct:+.2f}%)")

        except Exception as e:
            lines.append(f"  {name}: Error ({str(e)[:50]})")

    # Add interpretive context
    lines.append("")
    lines.append("  Interpretation Guide:")
    lines.append("  - VIX > 25 = High fear/volatility, reduce position sizes")
    lines.append("  - VIX < 15 = Low vol, potential complacency")
    lines.append("  - DXY rising = Pressure on equities and gold")
    lines.append("  - US10Y rising = Rate-sensitive sectors under pressure")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  4. ECONOMIC CALENDAR
# ═══════════════════════════════════════════════════════════

def get_economic_calendar() -> str:
    """
    Provide awareness of major scheduled economic events.
    Uses a static high-impact events list since free calendar APIs are unreliable.
    """
    now = datetime.utcnow()
    day_of_week = now.strftime("%A")
    hour = now.hour

    warnings = []

    # Known high-impact recurring events (UTC times)
    # These are general awareness - not a real-time calendar
    if day_of_week == "Wednesday":
        if 18 <= hour <= 20:
            warnings.append("⚠️ FOMC / Fed minutes typically release Wed 2PM ET (18:00 UTC). HIGH VOLATILITY EXPECTED.")

    if day_of_week == "Friday":
        if 12 <= hour <= 14:
            warnings.append("⚠️ NFP (Non-Farm Payrolls) releases first Friday of month at 8:30 AM ET. Check if today is NFP day.")

    if day_of_week in ["Tuesday", "Wednesday", "Thursday"]:
        if 12 <= hour <= 14:
            warnings.append("ℹ️ CPI/PPI data often releases Tue-Thu at 8:30 AM ET. Check economic calendar.")

    # Market hours awareness
    if day_of_week in ["Saturday", "Sunday"]:
        warnings.append("📅 Weekend: Futures markets have limited Sunday evening liquidity. Crypto trades 24/7.")
    elif hour < 13 or hour > 21:  # Before 8AM ET or after 4PM ET
        warnings.append("🕐 Outside regular US market hours. Futures active but lower liquidity. Watch for overnight gaps.")
    elif 13 <= hour <= 14:  # 8-9 AM ET
        warnings.append("🔔 US market open approaching/just opened. Expect high volatility first 30 minutes.")
    elif 19 <= hour <= 20:  # 2-3 PM ET
        warnings.append("🔔 Power hour approaching. Institutional volume increases into the close.")

    # General advice
    warnings.append(f"📆 Current UTC time: {now.strftime('%Y-%m-%d %H:%M')} ({day_of_week})")
    warnings.append("💡 Always check forexfactory.com or investing.com/economic-calendar before trading.")

    return "═══ ECONOMIC CALENDAR ═══\n" + "\n".join(f"  {w}" for w in warnings)


# ═══════════════════════════════════════════════════════════
#  AI WRAPPER
# ═══════════════════════════════════════════════════════════

async def ask_ai(role: str, prompt: str, max_tokens: int = 300) -> str:
    if not client:
        await asyncio.sleep(1)
        return f"[{role}] Mock response - missing API key."

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[
                {"role": "system", "content": f"You are a hedge fund {role}. Provide decisive, data-driven analysis. Reference the exact indicator values provided. Be specific about price levels."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error querying {role}: {str(e)}"


# ═══════════════════════════════════════════════════════════
#  MAIN ANALYSIS STREAM
# ═══════════════════════════════════════════════════════════

async def generate_analysis_stream(req: AnalysisRequest):
    ticker = req.ticker.upper()
    tf = req.timeframe
    risk = req.riskProfile

    def emit(marker: str, data: dict):
        return f"data: [{marker}] {json.dumps(data)}\n\n"

    try:
        # ── 0. Fetch ALL data concurrently ──
        loop = asyncio.get_event_loop()

        mtf_future = loop.run_in_executor(executor, fetch_multi_timeframe_data, ticker, tf)
        context_future = loop.run_in_executor(executor, fetch_market_context)
        calendar_future = loop.run_in_executor(executor, get_economic_calendar)

        mtf_data, market_context, econ_calendar = await asyncio.gather(
            mtf_future, context_future, calendar_future
        )

        # Build the comprehensive data package
        mtf_summary = build_mtf_summary(mtf_data, ticker)
        primary_indicators = list(mtf_data["indicators"].values())[0] if mtf_data["indicators"] else {}
        current_price = primary_indicators.get("current_price", "UNKNOWN")

        # Full data context string
        full_data = f"""
{mtf_summary}

{market_context}

{econ_calendar}
"""

        price_anchor = (
            f"\n\nCRITICAL: The CURRENT LIVE PRICE of {ticker} is {current_price}. "
            f"ALL entry zones, stop losses, and take profits MUST be within a realistic "
            f"range of this price. DO NOT hallucinate prices."
        )

        # ── 1. ANALYST TEAM ──
        analysts = {
            "FUNDAMENTAL_ANALYST": (
                f"Analyze {ticker} fundamentals. Current price: {current_price}. "
                f"Reference these real indicators:\n{mtf_summary}\n{market_context}"
            ),
            "SENTIMENT_ANALYST": (
                f"Analyze retail and institutional sentiment for {ticker}. "
                f"Current price: {current_price}. Volume ratio: {primary_indicators.get('volume_ratio', 'N/A')}x average. "
                f"RSI: {primary_indicators.get('RSI_14', 'N/A')}. "
                f"Context:\n{market_context}"
            ),
            "NEWS_ANALYST": (
                f"Analyze macroeconomic factors impacting {ticker}. "
                f"Current price: {current_price}.\n{market_context}\n{econ_calendar}"
            ),
            "TECHNICAL_ANALYST": (
                f"Provide technical analysis for {ticker} using these REAL computed indicators. "
                f"Reference the exact values below. Do NOT make up indicator values.\n"
                f"{mtf_summary}\n{price_anchor}"
            ),
        }

        analyst_outputs = {}
        for role, prompt in analysts.items():
            text = await ask_ai(role, prompt)
            analyst_outputs[role] = text
            yield emit(role, {"text": text})

        # ── 2. RESEARCHER DEBATE ──
        context = json.dumps(analyst_outputs)

        bear_prompt = (
            f"Using this analyst data and REAL indicators: {context}\n"
            f"Full data:\n{full_data}\n"
            f"Argue the BEARISH case against {ticker} at {current_price}. "
            f"Use specific indicator values to support your argument."
        )
        bear_text = await ask_ai("BEAR_RESEARCHER", bear_prompt, 300)
        yield emit("BEAR_RESEARCHER", {"text": bear_text})

        bull_prompt = (
            f"Using this analyst data and REAL indicators: {context}\n"
            f"Full data:\n{full_data}\n"
            f"Argue the BULLISH case for {ticker} at {current_price}. "
            f"Use specific indicator values to defend your position."
        )
        bull_text = await ask_ai("BULL_RESEARCHER", bull_prompt, 300)
        yield emit("BULL_RESEARCHER", {"text": bull_text})

        # ── 3. TRADER & RISK ──
        trader_prompt = (
            f"Review bull/bear arguments for {ticker}. Current price: {current_price}. "
            f"Key levels: ATR={primary_indicators.get('ATR_14', 'N/A')}, "
            f"BB upper={primary_indicators.get('BB_upper', 'N/A')}, "
            f"BB lower={primary_indicators.get('BB_lower', 'N/A')}, "
            f"VWAP={primary_indicators.get('VWAP', 'N/A')}. "
            f"Timeframe: {tf}. Be decisive about direction and exact levels."
        )
        trader_text = await ask_ai("TRADER_DECISION", trader_prompt, 250)
        yield emit("TRADER_DECISION", {"text": trader_text})

        atr_val = primary_indicators.get("ATR_14", 0)
        risk_prompt = (
            f"Review the trader's plan for {ticker} at {current_price}. "
            f"ATR(14) = {atr_val} (use this for stop loss sizing). "
            f"Risk profile: {risk}. "
            f"VIX context:\n{market_context}\n"
            f"Do we approve? Size recommendation in % of portfolio."
        )
        risk_text = await ask_ai("RISK_MANAGER", risk_prompt, 250)
        yield emit("RISK_MANAGER", {"text": risk_text})

        # ── 4. SIGNAL ENGINE ──
        # Use ATR for realistic SL/TP calculations
        atr_num = float(atr_val) if atr_val and atr_val != "N/A" else (float(current_price) * 0.005 if isinstance(current_price, (int, float)) else 50)
        cp = float(current_price) if isinstance(current_price, (int, float)) else 0

        json_prompt = f"""
Based on all previous context for {ticker} on {tf} timeframe, risk profile '{risk}':

CRITICAL PRICE DATA (USE THESE EXACT VALUES):
- Current price: {current_price}
- ATR(14): {atr_val} (use 1-2x ATR for stop loss distance)
- RSI(14): {primary_indicators.get('RSI_14', 'N/A')}
- MACD histogram: {primary_indicators.get('MACD_histogram', 'N/A')}
- EMA 9/21 cross: {primary_indicators.get('EMA_9_21_cross', 'N/A')}
- Price vs VWAP: {primary_indicators.get('price_vs_VWAP', 'N/A')}
- BB upper: {primary_indicators.get('BB_upper', 'N/A')}
- BB lower: {primary_indicators.get('BB_lower', 'N/A')}
- ADX: {primary_indicators.get('ADX', 'N/A')}

RULES:
- Entry zone: within 0.5x ATR of {current_price}
- Stop loss: 1-2x ATR from entry ({round(cp - atr_num * 1.5, 2)} to {round(cp - atr_num, 2)} for LONG)
- Take profit 1: 1.5-2x ATR from entry
- Take profit 2: 2.5-3x ATR from entry
- If RSI > 75 or < 25, reduce confidence
- If ADX < 20, market is ranging - reduce confidence
- If multi-timeframe trends conflict, reduce confidence

Output ONLY valid JSON. No markdown, no code blocks:
{{
    "ticker": "{ticker}",
    "timestamp_utc": "{datetime.utcnow().isoformat()}Z",
    "timeframe": "{tf}",
    "market_regime": "trend_day_up|trend_day_down|range_day|high_vol_news|low_liquidity",
    "signal": "LONG|SHORT|NO_TRADE",
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
    "indicators_used": {{
        "RSI_14": {primary_indicators.get('RSI_14', 'null')},
        "MACD_histogram": {primary_indicators.get('MACD_histogram', 'null')},
        "ATR_14": {primary_indicators.get('ATR_14', 'null')},
        "ADX": {primary_indicators.get('ADX', 'null')}
    }}
}}
"""
        signal_text = await ask_ai("SIGNAL_ENGINE", json_prompt, 600)
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

        yield emit("SIGNAL_ENGINE", signal_data)

    except Exception as e:
        yield emit("ERROR", {"text": f"Backend stream failed: {str(e)}"})


@app.post("/api/v1/analyze")
async def analyze_endpoint(request: AnalysisRequest):
    return StreamingResponse(
        generate_analysis_stream(request),
        media_type="text/event-stream"
    )

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "war-room-ai", "version": "2.0-sprint1"}
