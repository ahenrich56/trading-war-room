"""
Pure pandas/numpy indicator computations (no pandas-ta dependency).
Extracted from main.py for modularity.
"""

import pandas as pd
import numpy as np


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
