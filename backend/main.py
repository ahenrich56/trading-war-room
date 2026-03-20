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

CONTEXT_TICKERS = {
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
    "SP500": "ES=F",
}

class AnalysisRequest(BaseModel):
    ticker: str
    timeframe: str
    riskProfile: str


def resolve_ticker(raw: str) -> str:
    return TICKER_MAP.get(raw.upper().strip(), raw.upper().strip())


# ═══════════════════════════════════════════════════════════
#  PURE PANDAS/NUMPY INDICATOR COMPUTATIONS (no pandas-ta)
# ═══════════════════════════════════════════════════════════

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 2) if not pd.isna(val) else None

def _macd(close: pd.Series, fast=12, slow=26, signal=9) -> dict:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "MACD_line": round(float(macd_line.iloc[-1]), 2) if not pd.isna(macd_line.iloc[-1]) else None,
        "MACD_signal": round(float(signal_line.iloc[-1]), 2) if not pd.isna(signal_line.iloc[-1]) else None,
        "MACD_histogram": round(float(histogram.iloc[-1]), 2) if not pd.isna(histogram.iloc[-1]) else None,
    }

def _bollinger(close: pd.Series, period=20, std_dev=2) -> dict:
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return {
        "BB_upper": round(float(upper.iloc[-1]), 2) if not pd.isna(upper.iloc[-1]) else None,
        "BB_mid": round(float(sma.iloc[-1]), 2) if not pd.isna(sma.iloc[-1]) else None,
        "BB_lower": round(float(lower.iloc[-1]), 2) if not pd.isna(lower.iloc[-1]) else None,
    }

def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> float:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    val = atr.iloc[-1]
    return round(float(val), 2) if not pd.isna(val) else None

def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> float:
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di))
    adx = dx.ewm(span=period, adjust=False).mean()
    val = adx.iloc[-1]
    return round(float(val), 2) if not pd.isna(val) else None

def _stoch_rsi(close: pd.Series, period=14, smooth_k=3, smooth_d=3) -> dict:
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min)
    k = stoch_rsi.rolling(smooth_k).mean() * 100
    d = k.rolling(smooth_d).mean()
    return {
        "StochRSI_K": round(float(k.iloc[-1]), 2) if not pd.isna(k.iloc[-1]) else None,
        "StochRSI_D": round(float(d.iloc[-1]), 2) if not pd.isna(d.iloc[-1]) else None,
    }

def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> float:
    tp = (high + low + close) / 3
    cumvol = volume.cumsum()
    cumtp = (tp * volume).cumsum()
    vwap = cumtp / cumvol
    val = vwap.iloc[-1]
    return round(float(val), 2) if not pd.isna(val) else None


def compute_indicators(df: pd.DataFrame) -> dict:
    """Compute all technical indicators from OHLCV using pure pandas/numpy."""
    if df.empty or len(df) < 20:
        return {"error": "Insufficient data for indicator computation"}

    indicators = {}
    try:
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        current_price = round(float(close.iloc[-1]), 2)
        indicators["current_price"] = current_price

        # RSI
        indicators["RSI_14"] = _rsi(close, 14)

        # MACD
        macd = _macd(close)
        indicators.update(macd)

        # Bollinger Bands
        bb = _bollinger(close)
        indicators.update(bb)

        # ATR
        indicators["ATR_14"] = _atr(high, low, close, 14)

        # ADX
        indicators["ADX"] = _adx(high, low, close, 14)

        # EMAs
        for period in [9, 21, 50, 200]:
            ema = _ema(close, period)
            if len(ema) > 0 and not pd.isna(ema.iloc[-1]):
                indicators[f"EMA_{period}"] = round(float(ema.iloc[-1]), 2)

        # VWAP
        try:
            indicators["VWAP"] = _vwap(high, low, close, volume)
        except Exception:
            pass

        # Stochastic RSI
        stoch = _stoch_rsi(close)
        indicators.update(stoch)

        # Volume analysis
        avg_vol = volume.rolling(20).mean()
        if len(avg_vol) > 0 and not pd.isna(avg_vol.iloc[-1]):
            cv = float(volume.iloc[-1])
            av = float(avg_vol.iloc[-1])
            indicators["current_volume"] = int(cv)
            indicators["avg_volume_20"] = int(av)
            indicators["volume_ratio"] = round(cv / av, 2) if av > 0 else 0

        # Derived conditions
        if "EMA_9" in indicators and "EMA_21" in indicators:
            indicators["EMA_9_21_cross"] = "BULLISH" if indicators["EMA_9"] > indicators["EMA_21"] else "BEARISH"

        if "VWAP" in indicators and indicators["VWAP"]:
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


def format_indicators_for_ai(indicators: dict, label: str) -> str:
    if "error" in indicators:
        return f"[{label}] {indicators['error']}"

    lines = [f"═══ {label} INDICATORS ═══"]
    lines.append(f"  Price: {indicators.get('current_price', 'N/A')}")

    ema_cross = indicators.get("EMA_9_21_cross", "N/A")
    adx = indicators.get("ADX", "N/A")
    lines.append(f"  Trend: EMA 9/21={ema_cross}, ADX={adx}")

    emas = [f"EMA{p}={indicators[f'EMA_{p}']}" for p in [9, 21, 50, 200] if f"EMA_{p}" in indicators]
    if emas:
        lines.append(f"  EMAs: {', '.join(emas)}")

    rsi = indicators.get("RSI_14", "N/A")
    rsi_cond = indicators.get("RSI_condition", "")
    lines.append(f"  RSI(14): {rsi} ({rsi_cond})")

    lines.append(f"  MACD: line={indicators.get('MACD_line', 'N/A')}, signal={indicators.get('MACD_signal', 'N/A')}, hist={indicators.get('MACD_histogram', 'N/A')}")
    lines.append(f"  StochRSI: K={indicators.get('StochRSI_K', 'N/A')}, D={indicators.get('StochRSI_D', 'N/A')}")
    lines.append(f"  ATR(14): {indicators.get('ATR_14', 'N/A')}")
    lines.append(f"  Bollinger: upper={indicators.get('BB_upper', 'N/A')}, mid={indicators.get('BB_mid', 'N/A')}, lower={indicators.get('BB_lower', 'N/A')}")
    lines.append(f"  VWAP: {indicators.get('VWAP', 'N/A')} (price {indicators.get('price_vs_VWAP', 'N/A')})")
    lines.append(f"  Volume ratio: {indicators.get('volume_ratio', 'N/A')}x avg")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  MULTI-TIMEFRAME ANALYSIS
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
    yf_symbol = resolve_ticker(ticker)
    configs = TIMEFRAME_CONFIG.get(primary_tf, TIMEFRAME_CONFIG["5m"])

    results = {}
    bars_data = None

    for interval, period, label in configs:
        try:
            tk = yf.Ticker(yf_symbol)
            df = tk.history(period=period, interval=interval)
            if df.empty:
                results[label] = {"error": f"No data for {interval}"}
                continue

            results[label] = compute_indicators(df)

            if interval == primary_tf or bars_data is None:
                recent = df.tail(10)
                bars_data = [{
                    "time": str(idx),
                    "O": round(float(row["Open"]), 2),
                    "H": round(float(row["High"]), 2),
                    "L": round(float(row["Low"]), 2),
                    "C": round(float(row["Close"]), 2),
                    "V": int(row["Volume"])
                } for idx, row in recent.iterrows()]

        except Exception as e:
            results[label] = {"error": str(e)}

    return {"indicators": results, "bars": bars_data or [], "symbol": yf_symbol}


def build_mtf_summary(mtf_data: dict, ticker: str) -> str:
    lines = [f"╔══════════════════════════════════════╗"]
    lines.append(f"║  MULTI-TIMEFRAME ANALYSIS: {ticker}")
    lines.append(f"╚══════════════════════════════════════╝\n")

    for label, indicators in mtf_data["indicators"].items():
        lines.append(format_indicators_for_ai(indicators, label))
        lines.append("")

    # MTF Confluence
    trends = []
    for label, ind in mtf_data["indicators"].items():
        if isinstance(ind, dict) and "EMA_9_21_cross" in ind:
            trends.append(f"{label}: {ind['EMA_9_21_cross']}")

    if trends:
        lines.append("═══ MTF TREND CONFLUENCE ═══")
        for t in trends:
            lines.append(f"  {t}")
        bullish = sum(1 for t in trends if "BULLISH" in t)
        bearish = sum(1 for t in trends if "BEARISH" in t)
        lines.append(f"  Alignment: {bullish} BULLISH / {bearish} BEARISH out of {len(trends)} timeframes")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  MARKET CONTEXT LAYER
# ═══════════════════════════════════════════════════════════

def fetch_market_context() -> str:
    lines = ["═══ MARKET CONTEXT ═══"]

    for name, symbol in CONTEXT_TICKERS.items():
        try:
            tk = yf.Ticker(symbol)
            df = tk.history(period="2d", interval="5m")
            if df.empty:
                lines.append(f"  {name}: No data")
                continue

            current = round(float(df["Close"].iloc[-1]), 2)
            day_df = tk.history(period="5d", interval="1d")
            if not day_df.empty and len(day_df) >= 2:
                prev_close = float(day_df["Close"].iloc[-2])
                pct = round(((current - prev_close) / prev_close) * 100, 2)
            else:
                pct = 0.0

            direction = "▲" if pct > 0 else "▼" if pct < 0 else "─"
            lines.append(f"  {name}: {current} ({direction} {pct:+.2f}%)")

        except Exception as e:
            lines.append(f"  {name}: Error ({str(e)[:50]})")

    lines.append("\n  Interpretation:")
    lines.append("  - VIX > 25 = High fear, reduce size")
    lines.append("  - DXY rising = Pressure on equities/gold")
    lines.append("  - US10Y rising = Rate-sensitive sectors under pressure")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
#  ECONOMIC CALENDAR
# ═══════════════════════════════════════════════════════════

def get_economic_calendar() -> str:
    now = datetime.utcnow()
    day = now.strftime("%A")
    hour = now.hour
    warnings = []

    if day == "Wednesday" and 18 <= hour <= 20:
        warnings.append("⚠️ FOMC typically releases Wed 2PM ET. HIGH VOLATILITY EXPECTED.")
    if day == "Friday" and 12 <= hour <= 14:
        warnings.append("⚠️ NFP releases first Friday at 8:30 AM ET. Check if today is NFP day.")
    if day in ["Tuesday", "Wednesday", "Thursday"] and 12 <= hour <= 14:
        warnings.append("ℹ️ CPI/PPI often releases Tue-Thu 8:30 AM ET. Check calendar.")

    if day in ["Saturday", "Sunday"]:
        warnings.append("📅 Weekend: Limited futures liquidity.")
    elif hour < 13 or hour > 21:
        warnings.append("🕐 Outside US regular hours. Lower liquidity.")
    elif 13 <= hour <= 14:
        warnings.append("🔔 US market open. Expect high volatility first 30 min.")
    elif 19 <= hour <= 20:
        warnings.append("🔔 Power hour. Institutional volume increasing.")

    warnings.append(f"📆 UTC: {now.strftime('%Y-%m-%d %H:%M')} ({day})")
    warnings.append("💡 Check forexfactory.com before trading.")

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
                {"role": "system", "content": f"You are a hedge fund {role}. Provide decisive, data-driven analysis. Reference exact indicator values provided. Be specific about price levels."},
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
        mtf_data, market_context, econ_calendar = await asyncio.gather(
            loop.run_in_executor(executor, fetch_multi_timeframe_data, ticker, tf),
            loop.run_in_executor(executor, fetch_market_context),
            loop.run_in_executor(executor, get_economic_calendar),
        )

        mtf_summary = build_mtf_summary(mtf_data, ticker)
        primary = list(mtf_data["indicators"].values())[0] if mtf_data["indicators"] else {}
        current_price = primary.get("current_price", "UNKNOWN")

        full_data = f"{mtf_summary}\n\n{market_context}\n\n{econ_calendar}"

        price_anchor = (
            f"\nCRITICAL: CURRENT LIVE PRICE of {ticker} is {current_price}. "
            f"ALL prices MUST be within realistic range of {current_price}. DO NOT hallucinate."
        )

        # ── 1. ANALYST TEAM ──
        analysts = {
            "FUNDAMENTAL_ANALYST": f"Analyze {ticker} fundamentals. Price: {current_price}.\n{mtf_summary}\n{market_context}",
            "SENTIMENT_ANALYST": f"Analyze sentiment for {ticker}. Price: {current_price}. Vol ratio: {primary.get('volume_ratio', 'N/A')}x. RSI: {primary.get('RSI_14', 'N/A')}.\n{market_context}",
            "NEWS_ANALYST": f"Analyze macro factors for {ticker}. Price: {current_price}.\n{market_context}\n{econ_calendar}",
            "TECHNICAL_ANALYST": f"Technical analysis for {ticker} using REAL computed indicators below. Reference exact values.\n{mtf_summary}{price_anchor}",
        }

        analyst_outputs = {}
        for role, prompt in analysts.items():
            text = await ask_ai(role, prompt)
            analyst_outputs[role] = text
            yield emit(role, {"text": text})

        # ── 2. RESEARCHER DEBATE ──
        context_str = json.dumps(analyst_outputs)

        bear_text = await ask_ai("BEAR_RESEARCHER",
            f"Using analyst data and REAL indicators: {context_str}\n{full_data}\n"
            f"Argue BEARISH case against {ticker} at {current_price}. Use specific indicator values.", 300)
        yield emit("BEAR_RESEARCHER", {"text": bear_text})

        bull_text = await ask_ai("BULL_RESEARCHER",
            f"Using analyst data and REAL indicators: {context_str}\n{full_data}\n"
            f"Argue BULLISH case for {ticker} at {current_price}. Use specific indicator values.", 300)
        yield emit("BULL_RESEARCHER", {"text": bull_text})

        # ── 3. TRADER & RISK ──
        trader_text = await ask_ai("TRADER_DECISION",
            f"Review bull/bear for {ticker}. Price: {current_price}. "
            f"ATR={primary.get('ATR_14', 'N/A')}, BB upper={primary.get('BB_upper', 'N/A')}, "
            f"BB lower={primary.get('BB_lower', 'N/A')}, VWAP={primary.get('VWAP', 'N/A')}. "
            f"Timeframe: {tf}. Be decisive.", 250)
        yield emit("TRADER_DECISION", {"text": trader_text})

        atr_val = primary.get("ATR_14", 0)
        risk_text = await ask_ai("RISK_MANAGER",
            f"Review trader plan for {ticker} at {current_price}. ATR(14)={atr_val}. "
            f"Risk profile: {risk}.\n{market_context}\nApprove? Size recommendation.", 250)
        yield emit("RISK_MANAGER", {"text": risk_text})

        # ── 4. SIGNAL ENGINE ──
        atr_num = float(atr_val) if atr_val and atr_val != "N/A" else (float(current_price) * 0.005 if isinstance(current_price, (int, float)) else 50)
        cp = float(current_price) if isinstance(current_price, (int, float)) else 0

        json_prompt = f"""
Based on all context for {ticker} on {tf}, risk profile '{risk}':

CRITICAL PRICE DATA:
- Current price: {current_price}
- ATR(14): {atr_val} (use 1-2x ATR for stop distance)
- RSI(14): {primary.get('RSI_14', 'N/A')}
- MACD histogram: {primary.get('MACD_histogram', 'N/A')}
- EMA 9/21 cross: {primary.get('EMA_9_21_cross', 'N/A')}
- Price vs VWAP: {primary.get('price_vs_VWAP', 'N/A')}
- BB upper: {primary.get('BB_upper', 'N/A')}
- BB lower: {primary.get('BB_lower', 'N/A')}
- ADX: {primary.get('ADX', 'N/A')}

RULES:
- Entry: within 0.5x ATR of {current_price}
- SL: 1-2x ATR from entry
- TP1: 1.5-2x ATR, TP2: 2.5-3x ATR
- RSI>75 or <25: reduce confidence
- ADX<20: ranging, reduce confidence
- MTF conflict: reduce confidence

Output ONLY valid JSON, no markdown:
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
    "indicators_used": {{"RSI_14": {primary.get('RSI_14', 'null')}, "MACD_histogram": {primary.get('MACD_histogram', 'null')}, "ATR_14": {primary.get('ATR_14', 'null')}, "ADX": {primary.get('ADX', 'null')}}}
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

        # Store signal in history and send Telegram alert
        await store_signal(signal_data)
        await send_telegram_alert(signal_data)

        yield emit("SIGNAL_ENGINE", signal_data)

    except Exception as e:
        yield emit("ERROR", {"text": f"Backend stream failed: {str(e)}"})


# ═══════════════════════════════════════════════════════════
#  SIGNAL HISTORY (In-memory, last 50 signals)
# ═══════════════════════════════════════════════════════════

signal_history: list[dict] = []
MAX_HISTORY = 50

async def store_signal(signal_data: dict):
    """Store a signal in the history buffer."""
    global signal_history
    signal_history.insert(0, signal_data)
    if len(signal_history) > MAX_HISTORY:
        signal_history = signal_history[:MAX_HISTORY]


# ═══════════════════════════════════════════════════════════
#  TELEGRAM BOT ALERTS
# ═══════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

async def send_telegram_alert(signal_data: dict):
    """Send a formatted signal alert to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return  # Telegram not configured, silently skip

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
#  CHART DATA ENDPOINT (for TradingView Lightweight Charts)
# ═══════════════════════════════════════════════════════════

class ChartRequest(BaseModel):
    ticker: str
    timeframe: str

@app.post("/api/v1/chart-data")
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

        return {
            "candles": candles,
            "indicators": {
                "ema9": ema9_data,
                "ema21": ema21_data,
                "vwap": vwap_data,
                "bb": bb,
            },
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
async def get_signal_history(limit: int = 20):
    """Return recent signal history."""
    return {"signals": signal_history[:limit], "total": len(signal_history)}

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "war-room-ai", "version": "3.0-sprint2"}

