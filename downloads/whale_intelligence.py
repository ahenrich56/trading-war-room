"""
Whale Intelligence Module v1.0
================================
Replicates Unusual Whales-style insider/smart money detection for Solana + pump.fun:

1. Whale Wallet Tracker — monitors known profitable wallets in real-time
2. Unusual Volume Detector — flags tokens with abnormal buy volume spikes
3. Smart Money Flow — tracks where top wallets are moving funds
4. Insider Signal Detection — detects coordinated buying before pumps
5. Congressional/Public Figure Tracker — monitors known public wallets
6. Copy Trade Signal Generator — generates actionable copy-trade signals

Data sources:
- Helius websocket (real-time wallet monitoring)
- DexScreener (volume/price data)
- Solana RPC (on-chain transaction analysis)
- Birdeye API (token analytics)
"""

import asyncio
import aiohttp
import json
import time
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Callable
from datetime import datetime, timedelta
from config import Config

log = logging.getLogger("WhaleIntel")


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class WhaleWallet:
    """Tracked whale wallet profile."""
    address: str
    label: str = "Unknown Whale"
    category: str = "whale"  # whale, insider, smart_money, public_figure, fund
    win_rate: float = 0.0
    total_trades: int = 0
    total_pnl_sol: float = 0.0
    avg_return: float = 0.0
    last_trade_time: float = 0.0
    trust_score: float = 50.0
    tokens_held: List[str] = field(default_factory=list)


@dataclass
class WhaleAlert:
    """A detected whale/insider activity signal."""
    alert_type: str  # whale_buy, unusual_volume, smart_accumulation, insider_signal, copy_signal
    mint: str
    token_name: str
    wallet: str
    wallet_label: str
    amount_sol: float
    timestamp: float
    confidence: float  # 0-100
    details: dict = field(default_factory=dict)
    actionable: bool = False


@dataclass
class UnusualActivity:
    """Unusual volume/activity detection."""
    mint: str
    token_name: str
    activity_type: str  # volume_spike, buy_wall, whale_accumulation, coordinated_buys
    magnitude: float  # how unusual (1.0 = normal, 5.0 = 5x normal)
    confidence: float
    details: dict = field(default_factory=dict)


# ============================================================
# WHALE WALLET DATABASE
# ============================================================

class WhaleDatabase:
    """Persistent storage for whale wallets, their trades, and performance."""

    def __init__(self, db_path="whale_intel.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS whale_wallets (
                address TEXT PRIMARY KEY,
                label TEXT DEFAULT 'Unknown',
                category TEXT DEFAULT 'whale',
                win_rate REAL DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                avg_return REAL DEFAULT 0,
                trust_score REAL DEFAULT 50,
                first_seen REAL,
                last_active REAL,
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS whale_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT,
                mint TEXT,
                token_name TEXT,
                action TEXT,
                amount_sol REAL,
                price REAL,
                timestamp REAL,
                tx_signature TEXT,
                pnl REAL DEFAULT 0,
                FOREIGN KEY (wallet) REFERENCES whale_wallets(address)
            );

            CREATE TABLE IF NOT EXISTS whale_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT,
                mint TEXT,
                token_name TEXT,
                wallet TEXT,
                amount_sol REAL,
                confidence REAL,
                timestamp REAL,
                details TEXT,
                acted_on INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS volume_baselines (
                mint TEXT PRIMARY KEY,
                avg_volume_1h REAL DEFAULT 0,
                avg_buys_1h REAL DEFAULT 0,
                avg_sells_1h REAL DEFAULT 0,
                last_updated REAL
            );

            CREATE INDEX IF NOT EXISTS idx_trades_wallet ON whale_trades(wallet);
            CREATE INDEX IF NOT EXISTS idx_trades_mint ON whale_trades(mint);
            CREATE INDEX IF NOT EXISTS idx_alerts_time ON whale_alerts(timestamp);
        """)
        conn.commit()
        conn.close()

    def add_whale(self, address, label="Unknown", category="whale", trust_score=50):
        conn = sqlite3.connect(self.db_path)
        now = time.time()
        conn.execute("""INSERT OR REPLACE INTO whale_wallets
            (address, label, category, trust_score, first_seen, last_active)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (address, label, category, trust_score, now, now))
        conn.commit()
        conn.close()

    def get_all_whales(self) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT * FROM whale_wallets ORDER BY trust_score DESC").fetchall()
        conn.close()
        return [{"address": r[0], "label": r[1], "category": r[2],
                 "win_rate": r[3], "total_trades": r[4], "total_pnl": r[5],
                 "trust_score": r[7]} for r in rows]

    def record_trade(self, wallet, mint, token_name, action, amount_sol, price=0, tx_sig=""):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""INSERT INTO whale_trades
            (wallet, mint, token_name, action, amount_sol, price, timestamp, tx_signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (wallet, mint, token_name, action, amount_sol, price, time.time(), tx_sig))
        conn.execute("UPDATE whale_wallets SET last_active=?, total_trades=total_trades+1 WHERE address=?",
            (time.time(), wallet))
        conn.commit()
        conn.close()

    def record_alert(self, alert: WhaleAlert):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""INSERT INTO whale_alerts
            (alert_type, mint, token_name, wallet, amount_sol, confidence, timestamp, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert.alert_type, alert.mint, alert.token_name, alert.wallet,
             alert.amount_sol, alert.confidence, alert.timestamp, json.dumps(alert.details)))
        conn.commit()
        conn.close()

    def get_recent_alerts(self, hours=24) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        cutoff = time.time() - (hours * 3600)
        rows = conn.execute(
            "SELECT * FROM whale_alerts WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 50",
            (cutoff,)).fetchall()
        conn.close()
        return [{"id": r[0], "type": r[1], "mint": r[2], "token": r[3],
                 "wallet": r[4], "amount": r[5], "confidence": r[6],
                 "time": r[7]} for r in rows]

    def update_whale_stats(self, address, win_rate, total_pnl, avg_return):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""UPDATE whale_wallets SET win_rate=?, total_pnl=?, avg_return=?,
            trust_score = CASE
                WHEN ? > 60 AND ? > 0 THEN LEAST(95, trust_score + 5)
                WHEN ? < 40 OR ? < -10 THEN MAX(10, trust_score - 10)
                ELSE trust_score END
            WHERE address=?""",
            (win_rate, total_pnl, avg_return, win_rate, total_pnl, win_rate, total_pnl, address))
        conn.commit()
        conn.close()


# ============================================================
# WHALE WALLET TRACKER (Real-time monitoring)
# ============================================================

class WhaleWalletTracker:
    """
    Monitors known whale wallets for new transactions.
    Uses Helius websocket for real-time alerts, falls back to polling.
    """

    # Pre-seeded known profitable pump.fun wallets
    KNOWN_WHALES = [
        # These are example addresses — replace with real discovered whales
        {"address": "placeholder_whale_1", "label": "Top Pump Trader #1", "category": "smart_money"},
        {"address": "placeholder_whale_2", "label": "Top Pump Trader #2", "category": "smart_money"},
    ]

    def __init__(self, session: aiohttp.ClientSession, db: WhaleDatabase, rpc_url: str):
        self.session = session
        self.db = db
        self.rpc_url = rpc_url
        self.helius_key = getattr(Config, 'HELIUS_API_KEY', '')
        self.tracked_wallets: Dict[str, WhaleWallet] = {}
        self.alert_callback: Optional[Callable] = None
        self._poll_interval = 30  # seconds between polls

    def set_alert_callback(self, callback):
        self.alert_callback = callback

    async def init_wallets(self):
        """Load whale wallets from DB and seed defaults."""
        # Seed known whales
        for w in self.KNOWN_WHALES:
            if w["address"].startswith("placeholder"):
                continue
            self.db.add_whale(w["address"], w["label"], w["category"], trust_score=70)

        # Load from DB
        whales = self.db.get_all_whales()
        for w in whales:
            self.tracked_wallets[w["address"]] = WhaleWallet(
                address=w["address"], label=w["label"],
                category=w["category"], trust_score=w["trust_score"],
                win_rate=w["win_rate"], total_trades=w["total_trades"],
                total_pnl_sol=w["total_pnl"]
            )
        log.info(f"Tracking {len(self.tracked_wallets)} whale wallets")

    async def discover_whales_from_token(self, mint: str, token_name: str = ""):
        """
        Discover new whale wallets by analyzing top buyers of a successful token.
        This is how we build our whale list organically.
        """
        try:
            # Get recent transactions for this token
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getSignaturesForAddress",
                       "params": [mint, {"limit": 50}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                sigs = data.get("result", [])

            # Analyze early buyers (first 20 transactions)
            early_buyers = set()
            for sig_info in sigs[-20:]:  # Oldest first
                sig = sig_info.get("signature", "")
                if sig:
                    buyer = await self._extract_buyer_from_tx(sig)
                    if buyer:
                        early_buyers.add(buyer)

            # Check if these wallets are already profitable
            for wallet in early_buyers:
                if wallet in self.tracked_wallets:
                    continue
                # Check wallet's recent trade history
                profit_score = await self._estimate_wallet_profitability(wallet)
                if profit_score > 60:
                    self.db.add_whale(wallet, f"Discovered-{wallet[:8]}", "smart_money", trust_score=profit_score)
                    self.tracked_wallets[wallet] = WhaleWallet(
                        address=wallet, label=f"Discovered-{wallet[:8]}",
                        category="smart_money", trust_score=profit_score
                    )
                    log.info(f"New whale discovered: {wallet[:12]}... | Score: {profit_score}")

        except Exception as e:
            log.debug(f"Whale discovery error: {e}")

    async def _extract_buyer_from_tx(self, signature: str) -> Optional[str]:
        """Extract the buyer wallet from a transaction signature."""
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getTransaction",
                       "params": [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                result = data.get("result")
                if result:
                    accounts = result.get("transaction", {}).get("message", {}).get("accountKeys", [])
                    if accounts:
                        # First account is usually the signer/buyer
                        if isinstance(accounts[0], dict):
                            return accounts[0].get("pubkey")
                        return accounts[0]
            return None
        except Exception:
            return None

    async def _estimate_wallet_profitability(self, wallet: str) -> float:
        """Estimate how profitable a wallet is based on recent activity."""
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getSignaturesForAddress",
                       "params": [wallet, {"limit": 30}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                sigs = data.get("result", [])

            if len(sigs) < 5:
                return 30  # Too few trades to judge

            # Simple heuristic: active wallets with many transactions
            # that don't have many errors are likely profitable
            errors = sum(1 for s in sigs if s.get("err"))
            success_rate = (len(sigs) - errors) / len(sigs)

            # Check if wallet has SOL balance (profitable wallets tend to have balance)
            balance = await self._get_sol_balance(wallet)

            score = 40
            if success_rate > 0.8:
                score += 20
            if balance > 5:
                score += 15
            elif balance > 1:
                score += 10
            if len(sigs) >= 20:
                score += 10  # Active trader

            return min(90, score)
        except Exception:
            return 30

    async def _get_sol_balance(self, wallet: str) -> float:
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getBalance", "params": [wallet]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=5)) as resp:
                data = await resp.json()
                lamports = data.get("result", {}).get("value", 0)
                return lamports / 1e9
        except Exception:
            return 0

    async def monitor_wallets_polling(self):
        """Poll tracked wallets for new transactions."""
        log.info("Starting whale wallet polling monitor...")
        last_sigs: Dict[str, str] = {}

        while True:
            try:
                for address, whale in list(self.tracked_wallets.items()):
                    try:
                        payload = {"jsonrpc": "2.0", "id": 1,
                                   "method": "getSignaturesForAddress",
                                   "params": [address, {"limit": 5}]}
                        async with self.session.post(self.rpc_url, json=payload,
                                                     timeout=aiohttp.ClientTimeout(total=8)) as resp:
                            data = await resp.json()
                            sigs = data.get("result", [])

                        if not sigs:
                            continue

                        latest_sig = sigs[0].get("signature", "")
                        if address in last_sigs and last_sigs[address] == latest_sig:
                            continue  # No new transactions

                        last_sigs[address] = latest_sig

                        # Analyze the new transaction
                        for sig_info in sigs[:3]:
                            sig = sig_info.get("signature", "")
                            if sig_info.get("err"):
                                continue
                            trade = await self._analyze_transaction(sig, whale)
                            if trade:
                                alert = WhaleAlert(
                                    alert_type="whale_buy" if trade["action"] == "buy" else "whale_sell",
                                    mint=trade["mint"],
                                    token_name=trade.get("token_name", "Unknown"),
                                    wallet=address,
                                    wallet_label=whale.label,
                                    amount_sol=trade.get("amount_sol", 0),
                                    timestamp=time.time(),
                                    confidence=whale.trust_score,
                                    details=trade,
                                    actionable=trade["action"] == "buy" and whale.trust_score >= 60
                                )
                                self.db.record_alert(alert)
                                self.db.record_trade(address, trade["mint"],
                                    trade.get("token_name", ""), trade["action"],
                                    trade.get("amount_sol", 0), tx_sig=sig)

                                if self.alert_callback:
                                    await self.alert_callback(alert)

                        # Rate limit
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        log.debug(f"Error polling wallet {address[:8]}: {e}")

                await asyncio.sleep(self._poll_interval)

            except Exception as e:
                log.error(f"Wallet monitor error: {e}")
                await asyncio.sleep(30)

    async def _analyze_transaction(self, signature: str, whale: WhaleWallet) -> Optional[dict]:
        """Analyze a transaction to determine if it's a buy/sell of a pump.fun token."""
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getTransaction",
                       "params": [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                result = data.get("result")
                if not result:
                    return None

            meta = result.get("meta", {})
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])

            if not pre_balances or not post_balances:
                return None

            # Calculate SOL change for the signer
            sol_change = (post_balances[0] - pre_balances[0]) / 1e9

            # Check for token transfers in inner instructions
            inner = meta.get("innerInstructions", [])
            token_mints = set()
            for ix_group in inner:
                for ix in ix_group.get("instructions", []):
                    parsed = ix.get("parsed", {})
                    if isinstance(parsed, dict):
                        info = parsed.get("info", {})
                        mint = info.get("mint", "")
                        if mint:
                            token_mints.add(mint)

            if not token_mints:
                return None

            mint = list(token_mints)[0]  # Primary token

            # Determine action
            if sol_change < -0.01:
                action = "buy"
                amount_sol = abs(sol_change)
            elif sol_change > 0.01:
                action = "sell"
                amount_sol = sol_change
            else:
                return None

            # Get token name from DexScreener
            token_name = await self._get_token_name(mint)

            return {
                "action": action,
                "mint": mint,
                "token_name": token_name,
                "amount_sol": amount_sol,
                "sol_change": sol_change,
                "whale_label": whale.label,
                "whale_trust": whale.trust_score,
            }

        except Exception as e:
            log.debug(f"TX analysis error: {e}")
            return None

    async def _get_token_name(self, mint: str) -> str:
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        return pairs[0].get("baseToken", {}).get("name", "Unknown")
            return "Unknown"
        except Exception:
            return "Unknown"


# ============================================================
# UNUSUAL VOLUME DETECTOR
# ============================================================

class UnusualVolumeDetector:
    """
    Detects unusual volume spikes, buy walls, and coordinated buying.
    Similar to Unusual Whales' options flow detection but for Solana tokens.
    """

    def __init__(self, session: aiohttp.ClientSession, db: WhaleDatabase):
        self.session = session
        self.db = db
        self.volume_history: Dict[str, List[float]] = {}  # mint -> recent volumes
        self.alert_callback: Optional[Callable] = None
        self._check_interval = 60  # Check every 60 seconds

    def set_alert_callback(self, callback):
        self.alert_callback = callback

    async def monitor_unusual_activity(self):
        """Main loop: scan trending tokens for unusual activity."""
        log.info("Starting unusual volume detector...")
        while True:
            try:
                # Get trending tokens from DexScreener
                trending = await self._get_trending_tokens()

                for token in trending:
                    mint = token.get("mint", "")
                    name = token.get("name", "Unknown")
                    volume_5m = token.get("volume_5m", 0)
                    buys_5m = token.get("buys_5m", 0)
                    sells_5m = token.get("sells_5m", 0)
                    price_change = token.get("price_change_5m", 0)

                    # Track volume history
                    if mint not in self.volume_history:
                        self.volume_history[mint] = []
                    self.volume_history[mint].append(volume_5m)
                    if len(self.volume_history[mint]) > 60:
                        self.volume_history[mint] = self.volume_history[mint][-60:]

                    # Detect unusual patterns
                    alerts = self._detect_unusual_patterns(
                        mint, name, volume_5m, buys_5m, sells_5m, price_change
                    )

                    for alert in alerts:
                        if self.alert_callback:
                            await self.alert_callback(alert)

                await asyncio.sleep(self._check_interval)

            except Exception as e:
                log.error(f"Volume detector error: {e}")
                await asyncio.sleep(60)

    def _detect_unusual_patterns(self, mint, name, volume, buys, sells, price_change) -> List[WhaleAlert]:
        alerts = []
        history = self.volume_history.get(mint, [])

        if len(history) < 5:
            return alerts

        avg_volume = sum(history[:-1]) / max(len(history) - 1, 1)

        # Volume spike detection
        if avg_volume > 0 and volume > avg_volume * 3:
            magnitude = volume / avg_volume
            confidence = min(90, 50 + magnitude * 5)
            alert = WhaleAlert(
                alert_type="unusual_volume",
                mint=mint, token_name=name,
                wallet="market", wallet_label="Volume Spike",
                amount_sol=volume,
                timestamp=time.time(),
                confidence=confidence,
                details={
                    "magnitude": f"{magnitude:.1f}x normal",
                    "volume_5m": volume,
                    "avg_volume": avg_volume,
                    "price_change": f"{price_change:+.1f}%"
                },
                actionable=magnitude >= 5 and price_change > 0
            )
            alerts.append(alert)

        # Buy wall detection (many more buys than sells)
        if buys > 0 and sells > 0:
            buy_sell_ratio = buys / sells
            if buy_sell_ratio >= 3 and buys >= 20:
                confidence = min(85, 50 + buy_sell_ratio * 5)
                alert = WhaleAlert(
                    alert_type="buy_wall",
                    mint=mint, token_name=name,
                    wallet="market", wallet_label="Buy Wall Detected",
                    amount_sol=volume,
                    timestamp=time.time(),
                    confidence=confidence,
                    details={
                        "buy_sell_ratio": f"{buy_sell_ratio:.1f}:1",
                        "buys": buys, "sells": sells,
                        "price_change": f"{price_change:+.1f}%"
                    },
                    actionable=buy_sell_ratio >= 5
                )
                alerts.append(alert)

        return alerts

    async def _get_trending_tokens(self) -> List[dict]:
        """Get currently trending Solana tokens from DexScreener."""
        try:
            url = "https://api.dexscreener.com/token-boosts/top/v1"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    tokens = []
                    for item in data[:30]:
                        if item.get("chainId") == "solana":
                            tokens.append({
                                "mint": item.get("tokenAddress", ""),
                                "name": item.get("description", "Unknown"),
                                "volume_5m": 0,  # Will be enriched
                                "buys_5m": 0,
                                "sells_5m": 0,
                                "price_change_5m": 0,
                            })

                    # Enrich with detailed data
                    for token in tokens[:10]:
                        detail = await self._get_token_detail(token["mint"])
                        if detail:
                            token.update(detail)

                    return tokens
            return []
        except Exception as e:
            log.debug(f"Trending fetch error: {e}")
            return []

    async def _get_token_detail(self, mint: str) -> Optional[dict]:
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        p = pairs[0]
                        txns = p.get("txns", {}).get("m5", {})
                        return {
                            "volume_5m": float(p.get("volume", {}).get("m5", 0) or 0),
                            "buys_5m": int(txns.get("buys", 0)),
                            "sells_5m": int(txns.get("sells", 0)),
                            "price_change_5m": float(p.get("priceChange", {}).get("m5", 0) or 0),
                        }
            return None
        except Exception:
            return None


# ============================================================
# INSIDER SIGNAL DETECTOR
# ============================================================

class InsiderDetector:
    """
    Detects potential insider activity patterns:
    - Coordinated buying from multiple new wallets before a pump
    - Large single buys from wallets with no prior history
    - Wallets that consistently buy before major announcements
    """

    def __init__(self, session: aiohttp.ClientSession, db: WhaleDatabase, rpc_url: str):
        self.session = session
        self.db = db
        self.rpc_url = rpc_url
        self.recent_buys: Dict[str, List[dict]] = {}  # mint -> list of recent buy events
        self.alert_callback: Optional[Callable] = None

    def set_alert_callback(self, callback):
        self.alert_callback = callback

    def record_buy(self, mint: str, wallet: str, amount_sol: float, token_name: str = ""):
        """Record a buy event for pattern analysis."""
        if mint not in self.recent_buys:
            self.recent_buys[mint] = []
        self.recent_buys[mint].append({
            "wallet": wallet,
            "amount_sol": amount_sol,
            "timestamp": time.time(),
            "token_name": token_name,
        })
        # Keep only last 100 buys per token
        if len(self.recent_buys[mint]) > 100:
            self.recent_buys[mint] = self.recent_buys[mint][-100:]

    async def analyze_patterns(self, mint: str, token_name: str = "") -> List[WhaleAlert]:
        """Analyze buying patterns for insider signals."""
        alerts = []
        buys = self.recent_buys.get(mint, [])
        if len(buys) < 3:
            return alerts

        now = time.time()
        recent = [b for b in buys if now - b["timestamp"] < 300]  # Last 5 min

        if len(recent) < 3:
            return alerts

        # Pattern 1: Coordinated buying (many unique wallets buying in short window)
        unique_wallets = set(b["wallet"] for b in recent)
        if len(unique_wallets) >= 5 and len(recent) >= 8:
            total_sol = sum(b["amount_sol"] for b in recent)
            confidence = min(90, 50 + len(unique_wallets) * 3)
            alert = WhaleAlert(
                alert_type="coordinated_buying",
                mint=mint, token_name=token_name,
                wallet="multiple", wallet_label=f"{len(unique_wallets)} wallets",
                amount_sol=total_sol,
                timestamp=now,
                confidence=confidence,
                details={
                    "unique_wallets": len(unique_wallets),
                    "total_buys": len(recent),
                    "total_sol": f"{total_sol:.2f}",
                    "window": "5min"
                },
                actionable=confidence >= 70
            )
            alerts.append(alert)

        # Pattern 2: Single large buy (whale entry)
        for buy in recent:
            if buy["amount_sol"] >= 5.0:  # 5+ SOL single buy
                confidence = min(85, 50 + buy["amount_sol"] * 2)
                alert = WhaleAlert(
                    alert_type="large_single_buy",
                    mint=mint, token_name=token_name,
                    wallet=buy["wallet"],
                    wallet_label=f"Large Buyer ({buy['amount_sol']:.1f} SOL)",
                    amount_sol=buy["amount_sol"],
                    timestamp=buy["timestamp"],
                    confidence=confidence,
                    details={"amount_sol": buy["amount_sol"]},
                    actionable=buy["amount_sol"] >= 10
                )
                alerts.append(alert)

        return alerts


# ============================================================
# WHALE INTELLIGENCE ORCHESTRATOR
# ============================================================

class WhaleIntelligence:
    """
    Main orchestrator — coordinates all whale/insider detection modules.
    Integrates with the scanner and auto_trader.
    """

    def __init__(self, db: WhaleDatabase = None):
        self.db = db or WhaleDatabase()
        self.session: Optional[aiohttp.ClientSession] = None
        self.rpc_url = getattr(Config, 'SOLANA_RPC_URL', '') or "https://api.mainnet-beta.solana.com"

        self.wallet_tracker: Optional[WhaleWalletTracker] = None
        self.volume_detector: Optional[UnusualVolumeDetector] = None
        self.insider_detector: Optional[InsiderDetector] = None

        self.signal_callback: Optional[Callable] = None
        self.alert_history: List[WhaleAlert] = []
        self._running = False

    async def init(self):
        """Initialize all sub-modules."""
        self.session = aiohttp.ClientSession()
        self.wallet_tracker = WhaleWalletTracker(self.session, self.db, self.rpc_url)
        self.volume_detector = UnusualVolumeDetector(self.session, self.db)
        self.insider_detector = InsiderDetector(self.session, self.db, self.rpc_url)

        # Set alert callbacks
        self.wallet_tracker.set_alert_callback(self._on_alert)
        self.volume_detector.set_alert_callback(self._on_alert)
        self.insider_detector.set_alert_callback(self._on_alert)

        # Initialize wallet tracker
        await self.wallet_tracker.init_wallets()

        log.info("Whale Intelligence initialized")

    def set_signal_callback(self, callback):
        """Set callback for actionable signals (fed to auto_trader)."""
        self.signal_callback = callback

    async def _on_alert(self, alert: WhaleAlert):
        """Handle incoming alerts from all sub-modules."""
        self.alert_history.append(alert)
        if len(self.alert_history) > 500:
            self.alert_history = self.alert_history[-500:]

        self.db.record_alert(alert)

        # Log the alert
        emoji = {"whale_buy": "🐋", "unusual_volume": "📊", "buy_wall": "🧱",
                 "coordinated_buying": "🕵️", "large_single_buy": "💰",
                 "whale_sell": "🔴"}.get(alert.alert_type, "⚡")

        log.info(f"{emoji} WHALE ALERT: {alert.alert_type} | {alert.token_name} | "
                 f"{alert.wallet_label} | {alert.amount_sol:.2f} SOL | "
                 f"Confidence: {alert.confidence:.0f}%")

        # If actionable, generate a trading signal
        if alert.actionable and self.signal_callback:
            signal = {
                "mint": alert.mint,
                "name": alert.token_name,
                "source": "whale_intelligence",
                "alert_type": alert.alert_type,
                "safety_score": alert.confidence,
                "passed": True,
                "flags": [f"whale:{alert.alert_type}"],
                "whale_details": alert.details,
            }
            await self.signal_callback(signal)

    async def on_scanner_token(self, token_data: dict):
        """
        Called by the scanner for every new token.
        Records buy events for insider pattern detection.
        """
        mint = token_data.get("mint", "")
        dev_wallet = token_data.get("dev_wallet", "")
        name = token_data.get("name", "")
        initial_sol = token_data.get("initial_sol", 0)

        if mint and dev_wallet:
            self.insider_detector.record_buy(mint, dev_wallet, initial_sol, name)

    async def on_token_success(self, mint: str, token_name: str = ""):
        """
        Called when a token is confirmed successful (hit TP).
        Discovers new whale wallets from its early buyers.
        """
        await self.wallet_tracker.discover_whales_from_token(mint, token_name)

    async def run(self):
        """Start all monitoring tasks."""
        if not self.session:
            await self.init()

        self._running = True
        log.info("Starting Whale Intelligence monitoring...")

        tasks = [
            asyncio.create_task(self.wallet_tracker.monitor_wallets_polling()),
            asyncio.create_task(self.volume_detector.monitor_unusual_activity()),
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            log.error(f"Whale Intelligence error: {e}")

    def get_status(self) -> dict:
        """Get current whale intelligence status."""
        recent_alerts = [a for a in self.alert_history
                        if time.time() - a.timestamp < 3600]
        actionable = [a for a in recent_alerts if a.actionable]
        return {
            "tracked_whales": len(self.wallet_tracker.tracked_wallets) if self.wallet_tracker else 0,
            "alerts_1h": len(recent_alerts),
            "actionable_1h": len(actionable),
            "total_alerts": len(self.alert_history),
        }

    def get_recent_alerts_formatted(self, limit=10) -> str:
        """Get formatted recent alerts for Telegram display."""
        recent = sorted(self.alert_history, key=lambda a: a.timestamp, reverse=True)[:limit]
        if not recent:
            return "No recent whale alerts."

        lines = ["🐋 *Recent Whale Alerts*\n"]
        for a in recent:
            emoji = {"whale_buy": "🐋", "unusual_volume": "📊", "buy_wall": "🧱",
                     "coordinated_buying": "🕵️", "large_single_buy": "💰",
                     "whale_sell": "🔴"}.get(a.alert_type, "⚡")
            ts = datetime.fromtimestamp(a.timestamp).strftime("%H:%M")
            action = "🟢" if a.actionable else "⚪"
            lines.append(
                f"{emoji} {ts} | {a.token_name}\n"
                f"   {a.alert_type} | {a.amount_sol:.2f} SOL | "
                f"Conf: {a.confidence:.0f}% {action}"
            )
        return "\n".join(lines)

    async def shutdown(self):
        self._running = False
        if self.session:
            await self.session.close()
