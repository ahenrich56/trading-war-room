"""
Backtesting engine and Kelly Criterion position sizing.
Extracted from main.py for modularity.
"""

import yfinance as yf

from indicators import _rsi, _macd, _ema, _atr
from data_fetcher import resolve_ticker


def calculate_strategy_score(ema9, ema21, rsi, macd_hist, adx=None, vol_ratio=None, current_price=None, vwap=None):
    """Deterministic, rule-based indicator scoring logic shared across AI signal, backtest, and watchlist."""
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
    if macd_hist is not None:
        if macd_hist > 0:
            score += 15
            signals.append(f"MACD histogram positive ({macd_hist})")
        else:
            score -= 15
            signals.append(f"MACD histogram negative ({macd_hist})")

    # Optional enhancements
    if adx is not None:
        if adx > 25:
            score = int(score * 1.3)
            signals.append(f"Strong trend (ADX={adx})")
        elif adx < 20:
            score = int(score * 0.5)
            signals.append(f"Weak trend (ADX={adx})")

    if vol_ratio is not None and vol_ratio > 1.5:
        score = int(score * 1.2)
        signals.append(f"High volume ({vol_ratio}x)")

    if current_price is not None and vwap is not None and vwap != current_price:
        if current_price > vwap:
            score += 5
        else:
            score -= 5

    # Determine quick direction (-100 to +100)
    score = max(-100, min(100, score))
    direction = "LONG" if score > 15 else "SHORT" if score < -15 else "NO_TRADE"

    return score, direction, signals


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

            # Quick indicator scoring
            rsi = _rsi(close, 14)
            macd = _macd(close)
            ema9 = float(_ema(close, 9).iloc[-1])
            ema21 = float(_ema(close, 21).iloc[-1])
            atr = _atr(high, low, close, 14) or 1
            hist = macd.get("MACD_histogram")

            score, direction, _ = calculate_strategy_score(ema9, ema21, rsi, hist)

            # Only trade if score is strong enough
            if direction != "NO_TRADE":
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
