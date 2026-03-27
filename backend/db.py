"""
SQLite database operations for signals and outcomes.
Extracted from main.py for modularity.
"""

import os
import json
import sqlite3
from datetime import datetime

from data_fetcher import resolve_ticker

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
    try:
        conn.execute("ALTER TABLE signals ADD COLUMN resolved INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            ticker TEXT NOT NULL,
            data TEXT NOT NULL,
            read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


async def store_signal(signal_data: dict):
    """Store a signal in the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO signals (data, resolved) VALUES (?, 0)", (json.dumps(signal_data),))
    conn.commit()
    conn.close()


def get_learning_context() -> str:
    """Build self-learning context string from recent outcomes."""
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
            ctx = f"SELF-LEARNING DATA ({wins}W/{losses}L, {win_rate}% win rate from {total} tracked signals):\n"
            for o in recent:
                ctx += f"  {o['ticker']} {o['signal']} -> {o['result']} ({o['pnl_pct']}%)\n"
            ctx += "Use this data to calibrate your confidence levels and avoid repeating losing patterns."
            return ctx
    except Exception:
        pass
    return ""


def get_signal_history(limit: int = 20) -> dict:
    """Return recent signal history from SQLite."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT data FROM signals ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    signals = [json.loads(row[0]) for row in rows]
    return {"signals": signals, "total": len(signals)}


def report_outcome(outcome_data: dict) -> dict:
    """Record a signal outcome for the self-learning loop."""
    outcome = {
        **outcome_data,
        "reported_at": datetime.utcnow().isoformat() + "Z",
    }
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO outcomes (data) VALUES (?)", (json.dumps(outcome),))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
    conn.close()
    return {"status": "recorded", "total_outcomes": total}


def get_outcomes() -> dict:
    """Get outcome history and performance stats."""
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


def store_alert(alert_type: str, ticker: str, data: dict):
    """Store a new alert."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO alerts (type, ticker, data) VALUES (?, ?, ?)",
        (alert_type, ticker, json.dumps(data)),
    )
    conn.commit()
    conn.close()


def get_alerts(since: str | None = None, limit: int = 30) -> list:
    """Return recent alerts, optionally filtered by timestamp."""
    conn = sqlite3.connect(DB_PATH)
    if since:
        rows = conn.execute(
            "SELECT id, type, ticker, data, read, created_at FROM alerts WHERE created_at > ? ORDER BY id DESC LIMIT ?",
            (since, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, type, ticker, data, read, created_at FROM alerts ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return [
        {"id": r[0], "type": r[1], "ticker": r[2], "data": json.loads(r[3]), "read": bool(r[4]), "created_at": r[5]}
        for r in rows
    ]


def mark_alerts_read(alert_ids: list[int] | None = None):
    """Mark alerts as read. If no IDs given, marks all unread."""
    conn = sqlite3.connect(DB_PATH)
    if alert_ids:
        placeholders = ",".join("?" for _ in alert_ids)
        conn.execute(f"UPDATE alerts SET read = 1 WHERE id IN ({placeholders})", alert_ids)
    else:
        conn.execute("UPDATE alerts SET read = 1 WHERE read = 0")
    conn.commit()
    conn.close()


def get_unread_count() -> int:
    """Return count of unread alerts."""
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM alerts WHERE read = 0").fetchone()[0]
    conn.close()
    return count


async def monitor_active_trades(executor, resolve_ticker_fn):
    """Background loop to track unresolved signals vs live market prices."""
    import asyncio
    import yfinance as yf

    while True:
        try:
            await asyncio.sleep(60)

            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute("SELECT id, data FROM signals WHERE resolved = 0 AND created_at >= datetime('now', '-1 day')").fetchall()

            if not rows:
                conn.close()
                continue

            signals_by_ticker = {}
            for row in rows:
                sid, data_str = row
                try:
                    data = json.loads(data_str)
                    ticker = data.get("ticker")
                    if not ticker:
                        conn.execute("UPDATE signals SET resolved = 1 WHERE id = ?", (sid,))
                        continue

                    if data.get("signal") == "NO_TRADE":
                        conn.execute("UPDATE signals SET resolved = 1 WHERE id = ?", (sid,))
                        continue

                    if ticker not in signals_by_ticker:
                        signals_by_ticker[ticker] = []
                    signals_by_ticker[ticker].append({"id": sid, "data": data})
                except json.JSONDecodeError:
                    conn.execute("UPDATE signals SET resolved = 1 WHERE id = ?", (sid,))

            conn.commit()

            for ticker, open_signals in signals_by_ticker.items():
                yf_symbol = resolve_ticker_fn(ticker)
                try:
                    loop = asyncio.get_event_loop()
                    tk = yf.Ticker(yf_symbol)
                    df = await loop.run_in_executor(executor, lambda: tk.history(period="1d", interval="1m"))

                    if df.empty:
                        continue

                    current_price = df['Close'].iloc[-1]

                    for sig_info in open_signals:
                        sid = sig_info["id"]
                        sig = sig_info["data"]
                        direction = sig.get("signal")
                        entry_zone = sig.get("entry_zone", {})

                        if "min" in entry_zone and "max" in entry_zone:
                            entry = (entry_zone["min"] + entry_zone["max"]) / 2
                        else:
                            entry = current_price

                        sl = sig.get("stop_loss", 0)
                        tps = sig.get("take_profit", [])
                        tp1 = tps[0]["price"] if tps and len(tps) > 0 else 0

                        if not sl or not tp1:
                            continue

                        outcome_result = None
                        pnl_pct = 0.0

                        if direction == "LONG":
                            if current_price <= sl:
                                outcome_result = "LOSS"
                                pnl_pct = ((sl - entry) / entry) * 100
                            elif current_price >= tp1:
                                outcome_result = "WIN"
                                pnl_pct = ((current_price - entry) / entry) * 100

                        elif direction == "SHORT":
                            if current_price >= sl:
                                outcome_result = "LOSS"
                                pnl_pct = ((entry - sl) / entry) * 100
                            elif current_price <= tp1:
                                outcome_result = "WIN"
                                pnl_pct = ((entry - current_price) / entry) * 100

                        if outcome_result:
                            outcome_dict = {
                                "ticker": ticker,
                                "signal": direction,
                                "entry": entry,
                                "result": outcome_result,
                                "pnl_pct": round(float(pnl_pct), 2),
                                "notes": f"Auto-resolved at {round(float(current_price), 2)}",
                                "reported_at": datetime.utcnow().isoformat() + "Z",
                            }
                            conn.execute("INSERT INTO outcomes (data) VALUES (?)", (json.dumps(outcome_dict),))
                            conn.execute("UPDATE signals SET resolved = 1 WHERE id = ?", (sid,))

                except Exception as e:
                    print(f"Error fetching live data for auto-tracker {ticker}: {e}")

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Monitor active trades crashed: {e}")
            import asyncio
            await asyncio.sleep(60)
