"""
Auto Trader v2.0 — Aggressive $10-to-$1K Strategy
===================================================
- Bankroll-percentage position sizing with compounding
- Take-profit at 3x, stop-loss at -40%
- Max 3 concurrent positions
- Real trade execution via PumpPortal API
- Paper trading mode for testing
- Full PnL tracking
"""

import asyncio
import aiohttp
import time
import json
import logging
from dataclasses import dataclass
from typing import Dict, Optional
from config import Config
from database import Database

log = logging.getLogger("AutoTrader")


@dataclass
class Position:
    mint: str
    name: str
    entry_price: float
    amount_sol: float
    tokens_held: float
    entry_time: float
    safety_score: float
    highest_price: float = 0.0
    status: str = "OPEN"


class AutoTrader:
    def __init__(self, db: Database):
        self.db = db
        self.positions: Dict[str, Position] = {}
        self.bankroll = float(Config.DEFAULT_BUY_AMOUNT_SOL)
        self.initial_bankroll = self.bankroll
        self.total_pnl = 0.0
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.peak_bankroll = self.bankroll
        self.max_drawdown = 0.0

        self.bankroll_pct = Config.BANKROLL_PCT
        self.tp_mult = Config.TAKE_PROFIT_MULTIPLIER
        self.sl_pct = Config.STOP_LOSS_MULTIPLIER
        self.max_positions = Config.MAX_CONCURRENT_POSITIONS
        self.max_daily_trades = Config.TRADES_PER_DAY
        self.paper_mode = Config.PAPER_TRADING_MODE

        self.session: Optional[aiohttp.ClientSession] = None
        self._monitor_task = None

    async def init(self):
        self.session = aiohttp.ClientSession()

    async def on_signal(self, signal: dict):
        """Called by scanner when a token passes all filters."""
        if not Config.AUTO_TRADER_ENABLED:
            return

        mint = signal.get("mint", "")
        name = signal.get("name", "Unknown")
        safety_score = signal.get("safety_score", 0)
        passed = signal.get("passed", False)

        if not passed:
            return
        if len(self.positions) >= self.max_positions:
            return
        if self.daily_trades >= self.max_daily_trades:
            return
        if mint in self.positions:
            return

        position_size = self.bankroll * self.bankroll_pct
        if position_size < 0.001:
            return

        if self.daily_pnl <= -Config.DAILY_LOSS_LIMIT_SOL:
            log.warning("Daily loss limit reached")
            return

        if self.bankroll < self.initial_bankroll * (1 - Config.MAX_DRAWDOWN_PCT):
            log.warning(f"Max drawdown reached. Bankroll: {self.bankroll:.4f} SOL")
            return

        success, result = await self.execute_buy(mint, name, position_size, safety_score)
        if success:
            log.info(f"BUY: {name} | {position_size:.4f} SOL | Score: {safety_score:.1f}")

    async def execute_buy(self, mint, name, amount_sol, safety_score):
        if self.paper_mode:
            return await self._paper_buy(mint, name, amount_sol, safety_score)
        return await self._live_buy(mint, name, amount_sol, safety_score)

    async def _paper_buy(self, mint, name, amount_sol, safety_score):
        entry_price = amount_sol
        tokens = amount_sol / max(entry_price, 0.0001)
        pos = Position(mint=mint, name=name, entry_price=entry_price,
                       amount_sol=amount_sol, tokens_held=tokens,
                       entry_time=time.time(), safety_score=safety_score,
                       highest_price=entry_price)
        self.positions[mint] = pos
        self.bankroll -= amount_sol
        self.daily_trades += 1
        self.total_trades += 1
        log.info(f"[PAPER] BUY {name} | {amount_sol:.4f} SOL | Bankroll: {self.bankroll:.4f}")
        return True, "paper_trade"

    async def _live_buy(self, mint, name, amount_sol, safety_score):
        try:
            url = f"https://pumpportal.fun/api/trade?api-key={Config.PUMPPORTAL_API_KEY}"
            payload = {"action": "buy", "mint": mint, "amount": amount_sol,
                       "denominatedInSol": "true", "slippage": 15,
                       "priorityFee": 0.0005, "pool": "auto"}
            if not self.session:
                await self.init()
            async with self.session.post(url, data=payload,
                                         timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tx_sig = data.get("signature", "unknown")
                    pos = Position(mint=mint, name=name, entry_price=amount_sol,
                                   amount_sol=amount_sol,
                                   tokens_held=float(data.get("tokensReceived", 0)),
                                   entry_time=time.time(), safety_score=safety_score,
                                   highest_price=amount_sol)
                    self.positions[mint] = pos
                    self.bankroll -= amount_sol
                    self.daily_trades += 1
                    self.total_trades += 1
                    log.info(f"[LIVE] BUY {name} | {amount_sol:.4f} SOL | TX: {tx_sig}")
                    return True, tx_sig
                else:
                    error = await resp.text()
                    log.error(f"Buy failed: {resp.status} - {error}")
                    return False, error
        except Exception as e:
            log.error(f"Buy error: {e}")
            return False, str(e)

    async def execute_sell(self, mint, reason="manual"):
        if mint not in self.positions:
            return False, "No position"
        pos = self.positions[mint]
        if self.paper_mode:
            return await self._paper_sell(mint, pos, reason)
        return await self._live_sell(mint, pos, reason)

    async def _paper_sell(self, mint, pos, reason):
        current_value = pos.amount_sol * (pos.highest_price / max(pos.entry_price, 0.0001))
        pnl = current_value - pos.amount_sol
        self.bankroll += pos.amount_sol + pnl
        self.total_pnl += pnl
        self.daily_pnl += pnl
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
        if self.bankroll > self.peak_bankroll:
            self.peak_bankroll = self.bankroll
        dd = (self.peak_bankroll - self.bankroll) / max(self.peak_bankroll, 0.001)
        if dd > self.max_drawdown:
            self.max_drawdown = dd
        del self.positions[mint]
        log.info(f"[PAPER] SELL {pos.name} | {reason} | PnL: {pnl:+.4f} SOL | Bankroll: {self.bankroll:.4f}")
        return True, f"paper_sell_{reason}"

    async def _live_sell(self, mint, pos, reason):
        try:
            url = f"https://pumpportal.fun/api/trade?api-key={Config.PUMPPORTAL_API_KEY}"
            payload = {"action": "sell", "mint": mint, "amount": "100%",
                       "denominatedInSol": "false", "slippage": 15,
                       "priorityFee": 0.0005, "pool": "auto"}
            if not self.session:
                await self.init()
            async with self.session.post(url, data=payload,
                                         timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    sol_received = float(data.get("solReceived", 0))
                    pnl = sol_received - pos.amount_sol
                    self.bankroll += sol_received
                    self.total_pnl += pnl
                    self.daily_pnl += pnl
                    if pnl > 0:
                        self.wins += 1
                    else:
                        self.losses += 1
                    if self.bankroll > self.peak_bankroll:
                        self.peak_bankroll = self.bankroll
                    dd = (self.peak_bankroll - self.bankroll) / max(self.peak_bankroll, 0.001)
                    if dd > self.max_drawdown:
                        self.max_drawdown = dd
                    del self.positions[mint]
                    tx_sig = data.get("signature", "unknown")
                    log.info(f"[LIVE] SELL {pos.name} | {reason} | PnL: {pnl:+.4f} SOL | TX: {tx_sig}")
                    return True, tx_sig
                else:
                    error = await resp.text()
                    log.error(f"Sell failed: {resp.status} - {error}")
                    return False, error
        except Exception as e:
            log.error(f"Sell error: {e}")
            return False, str(e)

    async def monitor_positions(self):
        """Background task: check TP/SL/trailing/timeout on all open positions."""
        log.info("Position monitor started")
        while True:
            try:
                if not self.positions:
                    await asyncio.sleep(5)
                    continue

                for mint in list(self.positions.keys()):
                    pos = self.positions.get(mint)
                    if not pos:
                        continue

                    current_price = await self._get_current_price(mint)
                    if current_price <= 0:
                        if time.time() - pos.entry_time > 300:
                            await self.execute_sell(mint, "timeout_no_price")
                        continue

                    if current_price > pos.highest_price:
                        pos.highest_price = current_price

                    mult = current_price / max(pos.entry_price, 0.0001)

                    # Take profit
                    if mult >= self.tp_mult:
                        await self.execute_sell(mint, f"TP_{mult:.1f}x")
                        continue

                    # Stop loss
                    if mult <= (1 - self.sl_pct):
                        await self.execute_sell(mint, f"SL_{mult:.2f}x")
                        continue

                    # Trailing stop after 2x: sell if drops 30% from peak
                    peak_mult = pos.highest_price / max(pos.entry_price, 0.0001)
                    if peak_mult >= 2.0:
                        trail_price = pos.highest_price * 0.7
                        if current_price <= trail_price:
                            await self.execute_sell(mint, f"TRAIL_{mult:.1f}x_from_{peak_mult:.1f}x")
                            continue

                    # Max hold time: 30 minutes
                    if time.time() - pos.entry_time > 1800:
                        await self.execute_sell(mint, f"TIMEOUT_{mult:.2f}x")
                        continue

                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"Monitor error: {e}")
                await asyncio.sleep(10)

    async def _get_current_price(self, mint):
        try:
            if not self.session:
                await self.init()
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        return float(pairs[0].get("priceNative", 0) or 0)
            return 0.0
        except Exception:
            return 0.0

    def get_status(self):
        wr = (self.wins / max(self.total_trades, 1)) * 100
        return {
            "bankroll": f"{self.bankroll:.4f} SOL",
            "total_pnl": f"{self.total_pnl:+.4f} SOL",
            "daily_pnl": f"{self.daily_pnl:+.4f} SOL",
            "total_trades": self.total_trades,
            "wins": self.wins, "losses": self.losses,
            "win_rate": f"{wr:.1f}%",
            "open_positions": len(self.positions),
            "max_drawdown": f"{self.max_drawdown:.1%}",
            "paper_mode": self.paper_mode,
        }

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.daily_trades = 0
        log.info("Daily counters reset")

    async def shutdown(self):
        for mint in list(self.positions.keys()):
            await self.execute_sell(mint, "shutdown")
        if self.session:
            await self.session.close()

    def run(self):
        loop = asyncio.get_event_loop()
        self._monitor_task = loop.create_task(self.monitor_positions())
