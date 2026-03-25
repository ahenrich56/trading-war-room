"""
Market data fetching, ticker mapping, and multi-timeframe analysis.
Extracted from main.py for modularity.
"""

from datetime import datetime

import yfinance as yf
import pandas as pd

from indicators import compute_indicators


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


def resolve_ticker(raw: str) -> str:
    return TICKER_MAP.get(raw.upper().strip(), raw.upper().strip())


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
