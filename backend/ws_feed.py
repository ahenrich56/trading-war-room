"""
WebSocket price feed — polls yfinance every 3 seconds for the latest candle
and broadcasts incremental updates to all connected clients.

Uses ETF proxies (QQQ for NQ, SPY for ES, etc.) for near-real-time data.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, Set

import yfinance as yf

# Futures → ETF map (same as in main.py chart endpoint)
REALTIME_MAP = {
    "NQ": "QQQ", "NQ1": "QQQ", "NQ=F": "QQQ",
    "ES": "SPY", "ES1": "SPY", "ES=F": "SPY",
    "YM": "DIA", "YM1": "DIA", "YM=F": "DIA",
    "GC": "GLD", "GC1": "GLD", "GC=F": "GLD",
    "CL": "USO", "CL1": "USO", "CL=F": "USO",
    "RTY": "IWM", "RTY1": "IWM", "RTY=F": "IWM",
    "SI": "SLV", "SI1": "SLV",
    "ZB": "TLT", "ZB1": "TLT",
    "BTC": "BTC-USD", "BTC1": "BTC-USD",
    "ETH": "ETH-USD", "ETH1": "ETH-USD",
}


def resolve_chart_symbol(ticker: str) -> str:
    t = ticker.upper().strip()
    return REALTIME_MAP.get(t, t)


class PriceFeed:
    """Manages per-symbol polling and broadcasts to WebSocket clients."""

    def __init__(self):
        # symbol -> set of asyncio.Queue (one per connected client)
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # symbol -> latest candle cache
        self._cache: Dict[str, dict] = {}
        # symbol -> polling task
        self._tasks: Dict[str, asyncio.Task] = {}

    def subscribe(self, symbol: str) -> asyncio.Queue:
        """Add a subscriber for a symbol. Returns a Queue that receives updates."""
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        if symbol not in self._subscribers:
            self._subscribers[symbol] = set()
        self._subscribers[symbol].add(q)

        # Start polling if not already running
        if symbol not in self._tasks or self._tasks[symbol].done():
            self._tasks[symbol] = asyncio.create_task(self._poll_loop(symbol))

        return q

    def unsubscribe(self, symbol: str, q: asyncio.Queue):
        """Remove a subscriber. Stops polling if no subscribers remain."""
        if symbol in self._subscribers:
            self._subscribers[symbol].discard(q)
            if not self._subscribers[symbol]:
                del self._subscribers[symbol]
                # Cancel polling task
                if symbol in self._tasks:
                    self._tasks[symbol].cancel()
                    del self._tasks[symbol]

    async def _poll_loop(self, symbol: str):
        """Poll yfinance every 3 seconds for the latest candle."""
        yf_symbol = resolve_chart_symbol(symbol)

        while symbol in self._subscribers and self._subscribers[symbol]:
            try:
                candle = await asyncio.to_thread(self._fetch_latest, yf_symbol)
                if candle:
                    cached = self._cache.get(symbol)
                    # Only broadcast if candle changed
                    if not cached or cached["time"] != candle["time"] or cached["close"] != candle["close"] or cached["volume"] != candle["volume"]:
                        self._cache[symbol] = candle
                        msg = json.dumps({"type": "candle", "data": candle})
                        dead_queues = []
                        for q in self._subscribers.get(symbol, set()):
                            try:
                                q.put_nowait(msg)
                            except asyncio.QueueFull:
                                dead_queues.append(q)
                        for dq in dead_queues:
                            self._subscribers[symbol].discard(dq)
            except Exception:
                pass  # Silently retry on next cycle

            await asyncio.sleep(3)

    @staticmethod
    def _fetch_latest(yf_symbol: str) -> dict | None:
        """Fetch the most recent 1-minute candle from yfinance."""
        try:
            tk = yf.Ticker(yf_symbol)
            df = tk.history(period="1d", interval="1m")
            if df.empty:
                return None
            row = df.iloc[-1]
            return {
                "time": int(row.name.timestamp()),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            }
        except Exception:
            return None


# Global singleton
price_feed = PriceFeed()
