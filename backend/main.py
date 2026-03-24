import os
import json
import asyncio
import sqlite3
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
from whale_intel import TradFiWhaleDetector

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


# ═══════════════════════════════════════════════════════════
#  ICT / SMART MONEY CONCEPTS (CHoCH, BOS, Order Blocks, FVG)
# ═══════════════════════════════════════════════════════════

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


def detect_ict_concepts(df: pd.DataFrame) -> dict:
    """Run all ICT/SMC detection algorithms on OHLCV data."""
    if df.empty or len(df) < 20:
        return {"error": "Insufficient data for ICT analysis"}

    try:
        high = df["High"]
        low = df["Low"]

        swings = _detect_swing_points(high, low)
        structure = _detect_structure(high, low)
        order_blocks = _detect_order_blocks(df)
        fvgs = _detect_fvg(df)

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
        lines.append(f"  {ob['type']}: Zone {ob['bottom']}-{ob['top']}")

    for fvg in ict_data.get("fair_value_gaps", []):
        lines.append(f"  {fvg['type']}: Gap {fvg['bottom']}-{fvg['top']} (size: {fvg['size']})")

    shs = ict_data.get("recent_swing_highs", [])
    sls = ict_data.get("recent_swing_lows", [])
    if shs:
        lines.append(f"  Key Resistance (Swing Highs): {', '.join(str(s['price']) for s in shs)}")
    if sls:
        lines.append(f"  Key Support (Swing Lows): {', '.join(str(s['price']) for s in sls)}")

    return "\n".join(lines)




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
    dataframes = {}
    bars_data = None

    for interval, period, label in configs:
        try:
            tk = yf.Ticker(yf_symbol)
            df = tk.history(period=period, interval=interval)
            if df.empty:
                results[label] = {"error": f"No data for {interval}"}
                continue

            results[label] = compute_indicators(df)
            dataframes[interval] = df  # Store raw DF for ICT

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

    return {"indicators": results, "bars": bars_data or [], "symbol": yf_symbol, "dataframes": dataframes}


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
        mtf_data, market_context, econ_calendar, whale_alerts = await asyncio.gather(
            loop.run_in_executor(executor, fetch_multi_timeframe_data, ticker, tf),
            loop.run_in_executor(executor, fetch_market_context),
            loop.run_in_executor(executor, get_economic_calendar),
            loop.run_in_executor(executor, whale_detector.analyze_ticker, ticker),
        )

        mtf_summary = build_mtf_summary(mtf_data, ticker)
        primary = list(mtf_data["indicators"].values())[0] if mtf_data["indicators"] else {}
        current_price = primary.get("current_price", "UNKNOWN")

        # ICT / Smart Money Concepts from primary timeframe
        primary_df = mtf_data.get("dataframes", {}).get(tf) if "dataframes" in mtf_data else None
        ict_data = {}
        ict_text = ""
        if primary_df is not None and not primary_df.empty:
            ict_data = detect_ict_concepts(primary_df)
            ict_text = format_ict_for_ai(ict_data)

        full_data = f"{mtf_summary}\n\n{ict_text}\n\n{market_context}\n\n{econ_calendar}"

        # ── 0a. Format Whale Alerts ──
        whale_text = ""
        if whale_alerts:
            whale_text = f"═══ SMART MONEY / WHALE FLOW ALERTS ═══\n"
            for w in whale_alerts:
                whale_text += f"  [{w.alert_type.upper()}] {w.details['label']}! Magnitude: {w.magnitude:.1f}x normal volume. Price direction: {w.details['price_change_pct']}. Confidence: {w.confidence:.0f}/100.\n"
            full_data += f"\n\n{whale_text}"
            # Stream the whale alerts to frontend immediately
            yield emit("WHALE_ALERTS", [w.__dict__ for w in whale_alerts])
        # ── 0b. Fetch self-learning context from outcomes DB ──
        learning_ctx = ""
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("SELECT data FROM outcomes ORDER BY id DESC LIMIT 100").fetchall()
            conn.close()
            outcome_list = [json.loads(row[0]) for row in rows]
            total = len(outcome_list)
            if total >= 5:
                wins = sum(1 for o in outcome_list if o["result"] == "WIN")
                losses = total - wins
                win_rate = round(wins / total * 100, 1)
                recent = outcome_list[:10]
                learning_ctx = f"SELF-LEARNING DATA ({wins}W/{losses}L, {win_rate}% win rate from {total} tracked signals):\n"
                for o in recent:
                    learning_ctx += f"  {o['ticker']} {o['signal']} -> {o['result']} ({o['pnl_pct']}%)\n"
                learning_ctx += "Use this data to calibrate your confidence levels and avoid repeating losing patterns."
        except Exception:
            pass  # Self-learning is optional, don't break analysis

        price_anchor = (
            f"\nCRITICAL: CURRENT LIVE PRICE of {ticker} is {current_price}. "
            f"ALL prices MUST be within realistic range of {current_price}. DO NOT hallucinate."
        )

        # ── 1. ANALYST TEAM ──
        analysts = {
            "FUNDAMENTAL_ANALYST": f"Analyze {ticker} fundamentals. Price: {current_price}.\n{mtf_summary}\n{market_context}",
            "SENTIMENT_ANALYST": f"Analyze sentiment for {ticker}. Price: {current_price}. Vol ratio: {primary.get('volume_ratio', 'N/A')}x. RSI: {primary.get('RSI_14', 'N/A')}.\n{market_context}",
            "NEWS_ANALYST": f"Analyze macro factors for {ticker}. Price: {current_price}.\n{market_context}\n{econ_calendar}",
            "TECHNICAL_ANALYST": f"Technical analysis for {ticker} using REAL computed indicators AND Smart Money Concepts below. Reference exact values, mention structure (BOS/CHoCH), order blocks, and FVGs.\n{mtf_summary}\n{ict_text}{price_anchor}",
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
            f"ATR={primary.get('ATR_14', 'N/A')}, BB upper={primary.get('BB_upper', 'N/A')}, "
            f"BB lower={primary.get('BB_lower', 'N/A')}, VWAP={primary.get('VWAP', 'N/A')}. "
            f"Timeframe: {tf}. Be decisive.", 250, learning_context=learning_ctx)
        yield emit("TRADER_DECISION", {"text": trader_text})

        atr_val = primary.get("ATR_14", 0)
        risk_text = await ask_ai("RISK_MANAGER",
            f"Review trader plan for {ticker} at {current_price}. ATR(14)={atr_val}. "
            f"Risk profile: {risk}.\n{market_context}\nApprove? Size recommendation.", 250, learning_context=learning_ctx)
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

        # Store signal in history and send Telegram alert
        await store_signal(signal_data)
        await send_telegram_alert(signal_data)

        yield emit("SIGNAL_ENGINE", signal_data)

    except Exception as e:
        yield emit("ERROR", {"text": f"Backend stream failed: {str(e)}"})


# ═══════════════════════════════════════════════════════════
#  PERSISTENT STORAGE (SQLite)
# ═══════════════════════════════════════════════════════════

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "war_room.db")

def _init_db():
    """Initialize SQLite database with signals and outcomes tables."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()

_init_db()


async def store_signal(signal_data: dict):
    """Store a signal in the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO signals (data) VALUES (?)", (json.dumps(signal_data),))
    conn.commit()
    conn.close()


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
    """Return recent signal history from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT data FROM signals ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    signals = [json.loads(row[0]) for row in rows]
    return {"signals": signals, "total": len(signals)}


# ═══════════════════════════════════════════════════════════
#  WATCHLIST SCANNER (Quick-scan multiple tickers)
# ═══════════════════════════════════════════════════════════

DEFAULT_WATCHLIST = ["NQ1", "ES1", "AAPL", "NVDA", "TSLA", "BTCUSD", "GOLD", "AMZN"]

class WatchlistRequest(BaseModel):
    tickers: list[str] = DEFAULT_WATCHLIST
    timeframe: str = "5m"

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

        # Score the opportunity (-100 to +100)
        score = 0
        signals = []

        # EMA cross direction
        if ema9 > ema21:
            score += 20
            signals.append("EMA9 > EMA21 (bullish)")
        else:
            score -= 20
            signals.append("EMA9 < EMA21 (bearish)")

        # RSI signals
        if rsi is not None:
            if rsi > 70:
                score -= 15
                signals.append(f"RSI overbought ({rsi})")
            elif rsi < 30:
                score += 15
                signals.append(f"RSI oversold ({rsi})")
            elif rsi > 55:
                score += 10
                signals.append(f"RSI bullish ({rsi})")
            elif rsi < 45:
                score -= 10
                signals.append(f"RSI bearish ({rsi})")

        # MACD histogram
        hist = macd.get("MACD_histogram")
        if hist is not None:
            if hist > 0:
                score += 15
                signals.append(f"MACD histogram positive ({hist})")
            else:
                score -= 15
                signals.append(f"MACD histogram negative ({hist})")

        # ADX trend strength
        if adx is not None and adx > 25:
            score = int(score * 1.3)  # Amplify score in strong trends
            signals.append(f"Strong trend (ADX={adx})")
        elif adx is not None and adx < 20:
            score = int(score * 0.5)  # Dampen score in weak trends
            signals.append(f"Weak trend (ADX={adx})")

        # Volume confirmation
        if vol_ratio > 1.5:
            score = int(score * 1.2)
            signals.append(f"High volume ({vol_ratio}x)")

        # Price vs VWAP
        if vwap:
            if current_price > vwap:
                score += 5
            else:
                score -= 5

        # Determine quick direction
        direction = "LONG" if score > 15 else "SHORT" if score < -15 else "NEUTRAL"

        return {
            "ticker": ticker,
            "symbol": yf_symbol,
            "price": current_price,
            "direction": direction,
            "score": max(-100, min(100, score)),
            "rsi": rsi,
            "macd_hist": hist,
            "adx": adx,
            "ema_cross": "BULLISH" if ema9 > ema21 else "BEARISH",
            "vol_ratio": vol_ratio,
            "atr": atr,
            "signals": signals[:4],
        }

    except Exception as e:
        return {"ticker": ticker, "error": str(e), "score": 0}


@app.post("/api/v1/watchlist")
async def watchlist_scan(request: WatchlistRequest):
    """Scan multiple tickers and rank by signal strength."""
    loop = asyncio.get_event_loop()

    # Scan all tickers concurrently
    tasks = [
        loop.run_in_executor(executor, quick_scan_ticker, t, request.timeframe)
        for t in request.tickers
    ]
    results = await asyncio.gather(*tasks)

    # Sort by absolute score (strongest signals first)
    results = sorted(results, key=lambda x: abs(x.get("score", 0)), reverse=True)

    # Find the best opportunity
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
    "deepseek/r1:free",
    "qwen/qwen3-coder:free",
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


class ConsensusRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"

@app.post("/api/v1/consensus")
async def multi_model_consensus(request: ConsensusRequest):
    """Run the same signal prompt through multiple AI models and aggregate."""
    ticker = request.ticker.upper()
    tf = request.timeframe

    # Fetch real data for the prompt
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

    # Query all models concurrently
    tasks = [ask_model(model, prompt) for model in CONSENSUS_MODELS]
    verdicts = await asyncio.gather(*tasks)

    # Aggregate consensus
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

    # Agreement score
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

class ICTRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"

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
#  BACKTESTING ENGINE
# ═══════════════════════════════════════════════════════════

class BacktestRequest(BaseModel):
    ticker: str
    timeframe: str = "5m"
    lookback_days: int = 5

def run_backtest(ticker: str, timeframe: str, lookback_days: int) -> dict:
    """Replay signal scoring against historical data and calculate performance."""
    yf_symbol = resolve_ticker(ticker)
    tf_map = {
        "1m": ("1m", "1d"), "5m": ("5m", f"{lookback_days}d"),
        "15m": ("15m", f"{lookback_days}d"), "1h": ("1h", f"{lookback_days}d"),
    }
    interval, period = tf_map.get(timeframe, ("5m", f"{lookback_days}d"))

    try:
        tk = yf.Ticker(yf_symbol)
        df = tk.history(period=period, interval=interval)

        if df.empty or len(df) < 50:
            return {"error": "Insufficient data for backtest"}

        trades = []
        equity_curve = [10000]  # Start with $10k
        current_idx = 30  # Start after warmup period

        while current_idx < len(df) - 10:
            window = df.iloc[:current_idx + 1]
            close = window["Close"]
            high = window["High"]
            low = window["Low"]
            volume = window["Volume"]

            # Quick indicator scoring (same as watchlist scanner)
            rsi = _rsi(close, 14)
            macd = _macd(close)
            ema9 = float(_ema(close, 9).iloc[-1])
            ema21 = float(_ema(close, 21).iloc[-1])
            atr = _atr(high, low, close, 14) or 1

            score = 0
            if ema9 > ema21: score += 20
            else: score -= 20
            if rsi and rsi > 70: score -= 15
            elif rsi and rsi < 30: score += 15
            elif rsi and rsi > 55: score += 10
            elif rsi and rsi < 45: score -= 10
            hist = macd.get("MACD_histogram")
            if hist and hist > 0: score += 15
            elif hist: score -= 15

            # Only trade if score is strong enough
            if abs(score) > 20:
                direction = "LONG" if score > 0 else "SHORT"
                entry_price = float(close.iloc[-1])
                sl = entry_price - (1.5 * atr) if direction == "LONG" else entry_price + (1.5 * atr)
                tp = entry_price + (2 * atr) if direction == "LONG" else entry_price - (2 * atr)

                # Simulate: check next 10 bars
                future = df.iloc[current_idx + 1:current_idx + 11]
                result = "OPEN"
                exit_price = entry_price
                for _, bar in future.iterrows():
                    h = float(bar["High"])
                    l = float(bar["Low"])
                    if direction == "LONG":
                        if l <= sl: result = "LOSS"; exit_price = sl; break
                        if h >= tp: result = "WIN"; exit_price = tp; break
                    else:
                        if h >= sl: result = "LOSS"; exit_price = sl; break
                        if l <= tp: result = "WIN"; exit_price = tp; break

                if result == "OPEN":
                    exit_price = float(future["Close"].iloc[-1]) if len(future) > 0 else entry_price
                    pnl = exit_price - entry_price if direction == "LONG" else entry_price - exit_price
                    result = "WIN" if pnl > 0 else "LOSS"

                pnl = exit_price - entry_price if direction == "LONG" else entry_price - exit_price
                pnl_pct = round((pnl / entry_price) * 100, 3)

                trades.append({
                    "direction": direction,
                    "entry": round(entry_price, 2),
                    "exit": round(exit_price, 2),
                    "sl": round(sl, 2),
                    "tp": round(tp, 2),
                    "result": result,
                    "pnl_pct": pnl_pct,
                    "score": score,
                })

                # Update equity
                pos_size = equity_curve[-1] * 0.02  # 2% risk
                dollar_pnl = pos_size * (pnl_pct / 100)
                equity_curve.append(round(equity_curve[-1] + dollar_pnl, 2))

                current_idx += 10  # Skip forward after trade
            else:
                current_idx += 5  # Skip forward if no signal

        # Calculate stats
        wins = [t for t in trades if t["result"] == "WIN"]
        losses = [t for t in trades if t["result"] == "LOSS"]
        total = len(trades)
        win_rate = round(len(wins) / total * 100, 1) if total > 0 else 0

        avg_win = round(sum(t["pnl_pct"] for t in wins) / len(wins), 3) if wins else 0
        avg_loss = round(sum(abs(t["pnl_pct"]) for t in losses) / len(losses), 3) if losses else 0
        profit_factor = round(sum(t["pnl_pct"] for t in wins) / sum(abs(t["pnl_pct"]) for t in losses), 2) if losses and sum(abs(t["pnl_pct"]) for t in losses) > 0 else 999

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0
        for eq in equity_curve:
            if eq > peak: peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd: max_dd = dd

        # Sharpe ratio (simplified)
        returns = [trades[i]["pnl_pct"] for i in range(len(trades))]
        if len(returns) > 1:
            avg_ret = sum(returns) / len(returns)
            std_ret = (sum((r - avg_ret) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe = round(avg_ret / std_ret, 2) if std_ret > 0 else 0
        else:
            sharpe = 0

        return {
            "ticker": ticker,
            "timeframe": timeframe,
            "total_trades": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": round(max_dd, 2),
            "final_equity": equity_curve[-1],
            "equity_change_pct": round((equity_curve[-1] - 10000) / 100, 2),
            "trades": trades[-10:],  # Last 10 trades
            "kelly_optimal_pct": calculate_kelly(win_rate / 100, avg_win, avg_loss),
        }

    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
#  KELLY CRITERION POSITION SIZING
# ═══════════════════════════════════════════════════════════

def calculate_kelly(win_rate: float, avg_win: float, avg_loss: float) -> dict:
    """Calculate Kelly Criterion optimal position size."""
    if avg_loss == 0 or win_rate == 0:
        return {"full_kelly": 0, "half_kelly": 0, "quarter_kelly": 0, "recommended": 0}

    b = avg_win / avg_loss  # win/loss ratio
    p = win_rate
    q = 1 - p

    full = round((b * p - q) / b * 100, 2)
    if full < 0:
        full = 0

    return {
        "full_kelly": full,
        "half_kelly": round(full / 2, 2),
        "quarter_kelly": round(full / 4, 2),
        "recommended": round(full / 4, 2),  # Quarter Kelly is safest
        "win_rate": round(win_rate * 100, 1),
        "avg_rr": round(b, 2),
        "edge": round((b * p - q) * 100, 2),
    }


@app.post("/api/v1/backtest")
async def backtest_endpoint(request: BacktestRequest):
    """Run a backtest against historical data."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(executor, run_backtest, request.ticker, request.timeframe, request.lookback_days)
    return result


# ═══════════════════════════════════════════════════════════
#  AI SELF-LEARNING LOOP
# ═══════════════════════════════════════════════════════════

class OutcomeReport(BaseModel):
    ticker: str
    signal: str
    entry: float
    result: str  # WIN or LOSS
    pnl_pct: float
    notes: str = ""

@app.post("/api/v1/outcomes/report")
async def report_outcome(report: OutcomeReport):
    """Report a signal outcome for the self-learning loop (SQLite)."""
    outcome = {
        **report.dict(),
        "reported_at": datetime.utcnow().isoformat() + "Z",
    }
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO outcomes (data) VALUES (?)", (json.dumps(outcome),))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    conn.close()
    return {"status": "recorded", "total_outcomes": total}

@app.get("/api/v1/outcomes")
async def get_outcomes():
    """Get outcome history and performance stats for the self-learning prompt (SQLite)."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT data FROM outcomes ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    outcome_list = [json.loads(row[0]) for row in rows]

    total = len(outcome_list)
    wins = sum(1 for o in outcome_list if o["result"] == "WIN")
    losses = sum(1 for o in outcome_list if o["result"] == "LOSS")
    win_rate = round(wins / total * 100, 1) if total > 0 else 0

    # Build self-learning context string for AI
    if total >= 5:
        recent = outcome_list[:10]
        context = f"SELF-LEARNING: {wins}W/{losses}L ({win_rate}% win rate) from {total} signals.\n"
        for o in recent:
            context += f"  {o['ticker']} {o['signal']} → {o['result']} ({o['pnl_pct']}%)\n"
    else:
        context = "SELF-LEARNING: Insufficient outcome data (<5 signals tracked)."

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "outcomes": outcome_list[:20],
        "learning_context": context,
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "war-room-ai", "version": "5.0-sprint4"}


@app.get("/api/v1/whale-alerts")
async def get_whale_alerts(ticker: str):
    """Fetch unusual volume and smart money alerts for a specific ticker."""
    loop = asyncio.get_event_loop()
    alerts = await loop.run_in_executor(executor, whale_detector.analyze_ticker, ticker.upper())
    return {"ticker": ticker.upper(), "alerts": [w.__dict__ for w in alerts]}
