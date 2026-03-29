"""
Top-Tier Pump.fun Token Scanner v2.0
=====================================
Multi-layer safety analysis combining:
1. Real-time websocket monitoring (PumpPortal)
2. On-chain safety analysis (RugCheck API)
3. Dev wallet history & creator scoring
4. Bundle/insider detection
5. Liquidity & holder distribution analysis
6. DexScreener market data
7. Social signal scoring
8. Smart money wallet tracking

Designed to achieve 0.7+ scanner quality (catches 70%+ of rugs).
"""

import asyncio
import websockets
import json
import aiohttp
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Dict, List
from config import Config
from database import Database

log = logging.getLogger("Scanner")


@dataclass
class TokenSafetyReport:
    mint: str
    name: str
    symbol: str
    timestamp: float = 0.0
    dev_wallet: str = ""
    initial_sol: float = 0.0
    initial_mcap: float = 0.0
    rugcheck_score: float = 0.0
    dev_history_score: float = 0.0
    bundle_score: float = 0.0
    holder_score: float = 0.0
    liquidity_score: float = 0.0
    social_score: float = 0.0
    smart_money_score: float = 0.0
    overall_score: float = 0.0
    risk_level: str = "UNKNOWN"
    flags: list = field(default_factory=list)
    passed: bool = False
    dex_volume_5m: float = 0.0
    dex_buys_5m: int = 0
    dex_sells_5m: int = 0
    price_change_5m: float = 0.0


class RugCheckClient:
    BASE_URL = "https://api.rugcheck.xyz/v1"

    def __init__(self, session, api_key=""):
        self.session = session
        self.api_key = api_key
        self._cache = {}
        self._cache_ttl = 300

    async def check_token(self, mint):
        if mint in self._cache:
            cached = self._cache[mint]
            if time.time() - cached["_ts"] < self._cache_ttl:
                return cached
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            url = f"{self.BASE_URL}/tokens/{mint}/report"
            async with self.session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    data["_ts"] = time.time()
                    self._cache[mint] = data
                    return data
                elif resp.status == 429:
                    log.warning("RugCheck rate limited")
                    await asyncio.sleep(2)
                    return {}
                return {}
        except Exception as e:
            log.error(f"RugCheck error: {e}")
            return {}

    def parse_report(self, data):
        if not data or "_ts" not in data:
            return 50.0, ["no_rugcheck_data"]
        score = 100.0
        flags = []
        risk = data.get("riskLevel", "").lower()
        if risk in ("danger", "high"):
            score -= 50
            flags.append("rugcheck_danger")
        elif risk in ("warn", "medium"):
            score -= 25
            flags.append("rugcheck_warning")
        if data.get("mintAuthority"):
            score -= 30
            flags.append("mint_authority_enabled")
        if data.get("freezeAuthority"):
            score -= 25
            flags.append("freeze_authority_enabled")
        top_holders = data.get("topHolders", [])
        if top_holders:
            top_pct = sum(h.get("pct", 0) for h in top_holders[:5])
            if top_pct > 50:
                score -= 30
                flags.append(f"top5_hold_{top_pct:.0f}pct")
            elif top_pct > 30:
                score -= 15
                flags.append(f"top5_hold_{top_pct:.0f}pct")
        if data.get("lpLocked"):
            score += 10
        elif data.get("lpBurned"):
            score += 15
        else:
            score -= 10
            flags.append("lp_not_locked")
        risks = data.get("risks", [])
        for r in risks:
            level = r.get("level", "").lower()
            if level in ("danger", "critical"):
                score -= 20
                flags.append(f"risk:{r.get('name', 'unknown')}")
            elif level == "warn":
                score -= 10
        return max(0, min(100, score)), flags


class DevWalletAnalyzer:
    def __init__(self, session, rpc_url, db_path="dev_wallets.db"):
        self.session = session
        self.rpc_url = rpc_url
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS dev_wallets (
            wallet TEXT PRIMARY KEY, total_launches INTEGER DEFAULT 0,
            rugs INTEGER DEFAULT 0, successes INTEGER DEFAULT 0,
            avg_peak_mcap REAL DEFAULT 0, last_launch_ts REAL DEFAULT 0,
            score REAL DEFAULT 50, updated_at REAL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS token_history (
            mint TEXT PRIMARY KEY, dev_wallet TEXT, launched_at REAL,
            peak_mcap REAL DEFAULT 0, was_rug INTEGER DEFAULT 0,
            final_status TEXT DEFAULT 'unknown')""")
        conn.commit()
        conn.close()

    async def analyze_dev(self, dev_wallet):
        flags = []
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT * FROM dev_wallets WHERE wallet = ?", (dev_wallet,)).fetchone()
        conn.close()
        if row:
            total, rugs, successes, avg_mcap, last_launch, db_score, _ = row[1:]
            if rugs >= 3:
                return 5.0, ["serial_rugger", f"rugs:{rugs}/{total}"]
            if successes >= 3 and rugs == 0:
                return 90.0, ["proven_dev", f"successes:{successes}"]
            if total > 0:
                rug_rate = rugs / total
                if rug_rate > 0.5:
                    score = 20.0
                    flags.append(f"high_rug_rate:{rug_rate:.0%}")
                elif rug_rate > 0.2:
                    score = 40.0
                    flags.append(f"some_rugs:{rugs}/{total}")
                else:
                    score = 60.0 + (successes / total) * 30
                    flags.append(f"decent_history:{successes}/{total}")
                if last_launch and (time.time() - last_launch) < 3600:
                    score -= 20
                    flags.append("rapid_launcher")
                return max(0, min(100, score)), flags
        try:
            tx_count = await self._get_tx_count(dev_wallet)
            if tx_count < 5:
                return 40.0, ["new_wallet"]
            elif tx_count < 50:
                return 50.0, ["low_activity_wallet"]
            else:
                return 60.0, ["established_wallet"]
        except Exception:
            return 50.0, ["dev_check_failed"]

    async def _get_tx_count(self, wallet):
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getSignaturesForAddress",
                       "params": [wallet, {"limit": 100}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                return len(data.get("result", []))
        except Exception:
            return -1

    def record_launch(self, dev_wallet, mint):
        conn = sqlite3.connect(self.db_path)
        now = time.time()
        conn.execute("""INSERT INTO dev_wallets (wallet, total_launches, last_launch_ts, updated_at)
            VALUES (?, 1, ?, ?) ON CONFLICT(wallet) DO UPDATE SET
            total_launches = total_launches + 1, last_launch_ts = ?, updated_at = ?""",
            (dev_wallet, now, now, now, now))
        conn.execute("INSERT OR IGNORE INTO token_history (mint, dev_wallet, launched_at) VALUES (?, ?, ?)",
            (mint, dev_wallet, now))
        conn.commit()
        conn.close()

    def record_outcome(self, mint, was_rug, peak_mcap=0):
        conn = sqlite3.connect(self.db_path)
        status = "rug" if was_rug else "success"
        conn.execute("UPDATE token_history SET was_rug=?, peak_mcap=?, final_status=? WHERE mint=?",
            (1 if was_rug else 0, peak_mcap, status, mint))
        row = conn.execute("SELECT dev_wallet FROM token_history WHERE mint=?", (mint,)).fetchone()
        if row:
            dev = row[0]
            if was_rug:
                conn.execute("UPDATE dev_wallets SET rugs = rugs + 1 WHERE wallet=?", (dev,))
            else:
                conn.execute("UPDATE dev_wallets SET successes = successes + 1 WHERE wallet=?", (dev,))
        conn.commit()
        conn.close()


class BundleDetector:
    def __init__(self, session, rpc_url):
        self.session = session
        self.rpc_url = rpc_url

    async def check_bundle(self, mint, dev_wallet):
        flags = []
        try:
            early_txs = await self._get_early_transactions(mint)
            if not early_txs:
                return 60.0, ["no_early_tx_data"]
            early_buyers = set()
            fast_buys = 0
            creation_time = None
            for tx in early_txs:
                if not creation_time:
                    creation_time = tx.get("blockTime", 0)
                tx_time = tx.get("blockTime", 0)
                if creation_time and tx_time and (tx_time - creation_time) < 2:
                    fast_buys += 1
            score = 80.0
            if fast_buys > 5:
                score -= 50
                flags.append(f"heavily_bundled:{fast_buys}_fast_buys")
            elif fast_buys > 3:
                score -= 35
                flags.append(f"bundled:{fast_buys}_fast_buys")
            elif fast_buys > 1:
                score -= 15
                flags.append(f"suspicious:{fast_buys}_fast_buys")
            return max(0, min(100, score)), flags
        except Exception as e:
            log.debug(f"Bundle check error: {e}")
            return 55.0, ["bundle_check_failed"]

    async def _get_early_transactions(self, mint):
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getSignaturesForAddress",
                       "params": [mint, {"limit": 20}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                return data.get("result", [])
        except Exception:
            return []


class DexScreenerClient:
    BASE_URL = "https://api.dexscreener.com"

    def __init__(self, session):
        self.session = session
        self._cache = {}

    async def get_token_data(self, mint):
        if mint in self._cache:
            if time.time() - self._cache[mint].get("_ts", 0) < 30:
                return self._cache[mint]
        try:
            url = f"{self.BASE_URL}/latest/dex/tokens/{mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        result = pairs[0]
                        result["_ts"] = time.time()
                        self._cache[mint] = result
                        return result
            return {}
        except Exception as e:
            log.debug(f"DexScreener error: {e}")
            return {}

    def parse_market_data(self, data):
        if not data:
            return {}
        txns = data.get("txns", {})
        m5 = txns.get("m5", {})
        h1 = txns.get("h1", {})
        return {
            "price_usd": float(data.get("priceUsd", 0) or 0),
            "volume_5m": float(m5.get("volume", 0) or 0),
            "buys_5m": int(m5.get("buys", 0) or 0),
            "sells_5m": int(m5.get("sells", 0) or 0),
            "volume_1h": float(h1.get("volume", 0) or 0),
            "buys_1h": int(h1.get("buys", 0) or 0),
            "sells_1h": int(h1.get("sells", 0) or 0),
            "liquidity_usd": float(data.get("liquidity", {}).get("usd", 0) or 0),
            "fdv": float(data.get("fdv", 0) or 0),
            "price_change_5m": float(data.get("priceChange", {}).get("m5", 0) or 0),
            "price_change_1h": float(data.get("priceChange", {}).get("h1", 0) or 0),
        }


class SmartMoneyTracker:
    def __init__(self, session, rpc_url, db_path="smart_money.db"):
        self.session = session
        self.rpc_url = rpc_url
        self.db_path = db_path
        self.watched_wallets = {}
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS smart_wallets (
            wallet TEXT PRIMARY KEY, label TEXT DEFAULT '',
            win_rate REAL DEFAULT 0, total_trades INTEGER DEFAULT 0,
            total_pnl REAL DEFAULT 0, added_at REAL DEFAULT 0,
            last_active REAL DEFAULT 0)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS smart_money_buys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, wallet TEXT, mint TEXT,
            bought_at REAL, amount_sol REAL DEFAULT 0)""")
        conn.commit()
        conn.close()

    def add_smart_wallet(self, wallet, label="", win_rate=0):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT OR REPLACE INTO smart_wallets (wallet, label, win_rate, added_at) VALUES (?,?,?,?)",
            (wallet, label, win_rate, time.time()))
        conn.commit()
        conn.close()
        self.watched_wallets[wallet] = {"label": label, "win_rate": win_rate}

    def load_wallets(self):
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT wallet, label, win_rate FROM smart_wallets").fetchall()
        conn.close()
        for w, l, wr in rows:
            self.watched_wallets[w] = {"label": l, "win_rate": wr}
        log.info(f"Loaded {len(self.watched_wallets)} smart money wallets")

    async def check_smart_money_interest(self, mint):
        if not self.watched_wallets:
            return 50.0, ["no_smart_wallets_configured"]
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getSignaturesForAddress",
                       "params": [mint, {"limit": 50}]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                sigs = data.get("result", [])
            smart_buys = 0
            smart_labels = []
            for sig in sigs:
                sig_str = json.dumps(sig)
                for wallet, info in self.watched_wallets.items():
                    if wallet[:16] in sig_str:
                        smart_buys += 1
                        smart_labels.append(info.get("label", wallet[:8]))
            if smart_buys >= 3:
                return 95.0, [f"strong_smart_money:{','.join(smart_labels[:3])}"]
            elif smart_buys >= 1:
                return 80.0, [f"smart_money_buy:{','.join(smart_labels[:2])}"]
            return 50.0, ["no_smart_money"]
        except Exception:
            return 50.0, ["smart_money_check_failed"]


class SocialAnalyzer:
    def __init__(self, session):
        self.session = session

    async def analyze_social(self, token_data, dex_data=None):
        score = 40.0
        flags = []
        uri = token_data.get("uri", "")
        name = token_data.get("name", "").lower()
        symbol = token_data.get("symbol", "").lower()
        if uri:
            try:
                metadata = await self._fetch_metadata(uri)
                if metadata:
                    if metadata.get("twitter") or metadata.get("x"):
                        score += 15
                        flags.append("has_twitter")
                    if metadata.get("telegram"):
                        score += 10
                        flags.append("has_telegram")
                    if metadata.get("website"):
                        score += 10
                        flags.append("has_website")
                    if metadata.get("description") and len(metadata.get("description", "")) > 20:
                        score += 5
                        flags.append("has_description")
            except Exception:
                pass
        if dex_data:
            info = dex_data.get("info", {})
            socials = info.get("socials", [])
            if socials:
                score += len(socials) * 5
                flags.append(f"dex_socials:{len(socials)}")
            websites = info.get("websites", [])
            if websites:
                score += 10
                flags.append("dex_website")
        trending = ["trump", "elon", "pepe", "doge", "ai", "gpt", "agent",
                     "cat", "dog", "moon", "based", "sol", "bonk"]
        for kw in trending:
            if kw in name or kw in symbol:
                score += 5
                flags.append(f"trending:{kw}")
                break
        return max(0, min(100, score)), flags

    async def _fetch_metadata(self, uri):
        try:
            if uri.startswith("ipfs://"):
                uri = f"https://ipfs.io/ipfs/{uri[7:]}"
            async with self.session.get(uri, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception:
            pass
        return {}


class HolderAnalyzer:
    def __init__(self, session, rpc_url):
        self.session = session
        self.rpc_url = rpc_url

    async def analyze_holders(self, mint):
        try:
            payload = {"jsonrpc": "2.0", "id": 1,
                       "method": "getTokenLargestAccounts", "params": [mint]}
            async with self.session.post(self.rpc_url, json=payload,
                                         timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                accounts = data.get("result", {}).get("value", [])
            if not accounts:
                return 50.0, ["no_holder_data"]
            amounts = [float(a.get("uiAmount", 0) or 0) for a in accounts]
            total = sum(amounts)
            if total == 0:
                return 50.0, ["zero_supply"]
            top1_pct = (amounts[0] / total * 100) if amounts else 0
            top5_pct = (sum(amounts[:5]) / total * 100) if len(amounts) >= 5 else top1_pct
            score = 80.0
            flags = []
            if top1_pct > 50:
                score -= 40
                flags.append(f"top1_holds_{top1_pct:.0f}pct")
            elif top1_pct > 30:
                score -= 20
                flags.append(f"top1_holds_{top1_pct:.0f}pct")
            if top5_pct > 80:
                score -= 30
                flags.append(f"top5_hold_{top5_pct:.0f}pct")
            elif top5_pct > 60:
                score -= 15
                flags.append(f"top5_hold_{top5_pct:.0f}pct")
            num_holders = len([a for a in amounts if a > 0])
            if num_holders < 5:
                score -= 20
                flags.append(f"only_{num_holders}_holders")
            elif num_holders > 20:
                score += 10
                flags.append(f"{num_holders}_holders")
            return max(0, min(100, score)), flags
        except Exception as e:
            log.debug(f"Holder analysis error: {e}")
            return 50.0, ["holder_check_failed"]


class TokenScanner:
    """Top-tier pump.fun scanner — orchestrates all analysis layers."""

    WEIGHTS = {
        "rugcheck": 0.25,
        "dev_history": 0.20,
        "bundle": 0.15,
        "holder": 0.10,
        "liquidity": 0.10,
        "social": 0.10,
        "smart_money": 0.10,
    }

    def __init__(self, db, signal_callback):
        self.db = db
        self.signal_callback = signal_callback
        self.uri = "wss://pumpportal.fun/api/data"
        self.rpc_url = getattr(Config, 'SOLANA_RPC_URL', '') or "https://api.mainnet-beta.solana.com"
        self.session = None
        self.rugcheck = None
        self.dev_analyzer = None
        self.bundle_detector = None
        self.dex_client = None
        self.smart_money = None
        self.social_analyzer = None
        self.holder_analyzer = None
        self._last_analysis_time = 0
        self._min_analysis_interval = 0.5
        self.tokens_seen = 0
        self.tokens_passed = 0
        self.tokens_rejected = 0

    async def _init_analyzers(self):
        self.session = aiohttp.ClientSession()
        self.rugcheck = RugCheckClient(self.session, api_key=getattr(Config, 'RUGCHECK_API_KEY', ''))
        self.dev_analyzer = DevWalletAnalyzer(self.session, self.rpc_url)
        self.bundle_detector = BundleDetector(self.session, self.rpc_url)
        self.dex_client = DexScreenerClient(self.session)
        self.smart_money = SmartMoneyTracker(self.session, self.rpc_url)
        self.social_analyzer = SocialAnalyzer(self.session)
        self.holder_analyzer = HolderAnalyzer(self.session, self.rpc_url)
        self.smart_money.load_wallets()

    async def scan_new_tokens(self):
        await self._init_analyzers()
        while True:
            try:
                log.info("Connecting to PumpPortal websocket...")
                async with websockets.connect(self.uri, ping_interval=20, ping_timeout=10) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    log.info("Subscribed to new token events")
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if data.get("txType") == "create":
                                asyncio.create_task(self._process_new_token(data))
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            log.error(f"Message error: {e}")
            except websockets.exceptions.ConnectionClosed:
                log.warning("WebSocket disconnected, reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                log.error(f"Scanner error: {e}, reconnecting in 10s...")
                await asyncio.sleep(10)

    async def _process_new_token(self, token_data):
        mint = token_data.get("mint", "")
        name = token_data.get("name", "Unknown")
        symbol = token_data.get("symbol", "???")
        dev_wallet = token_data.get("traderPublicKey", "")
        initial_sol = float(token_data.get("vSolInBondingCurve", 0) or 0)
        self.tokens_seen += 1

        now = time.time()
        elapsed = now - self._last_analysis_time
        if elapsed < self._min_analysis_interval:
            await asyncio.sleep(self._min_analysis_interval - elapsed)
        self._last_analysis_time = time.time()

        log.info(f"New token: {name} ({symbol}) | {mint[:12]}... | Dev: {dev_wallet[:12]}...")
        self.dev_analyzer.record_launch(dev_wallet, mint)

        report = TokenSafetyReport(
            mint=mint, name=name, symbol=symbol,
            timestamp=time.time(), dev_wallet=dev_wallet,
            initial_sol=initial_sol,
            initial_mcap=initial_sol * 150
        )

        try:
            results = await asyncio.gather(
                self.rugcheck.check_token(mint),
                self.dev_analyzer.analyze_dev(dev_wallet),
                self.bundle_detector.check_bundle(mint, dev_wallet),
                self.holder_analyzer.analyze_holders(mint),
                self.social_analyzer.analyze_social(token_data),
                self.smart_money.check_smart_money_interest(mint),
                return_exceptions=True
            )

            all_flags = []

            # 1. RugCheck
            if isinstance(results[0], dict):
                rc_score, rc_flags = self.rugcheck.parse_report(results[0])
                report.rugcheck_score = rc_score
                all_flags.extend(rc_flags)
            else:
                report.rugcheck_score = 50.0

            # 2. Dev history
            if isinstance(results[1], tuple):
                report.dev_history_score, dev_flags = results[1]
                all_flags.extend(dev_flags)
            else:
                report.dev_history_score = 50.0

            # 3. Bundle detection
            if isinstance(results[2], tuple):
                report.bundle_score, bundle_flags = results[2]
                all_flags.extend(bundle_flags)
            else:
                report.bundle_score = 55.0

            # 4. Holder distribution
            if isinstance(results[3], tuple):
                report.holder_score, holder_flags = results[3]
                all_flags.extend(holder_flags)
            else:
                report.holder_score = 50.0

            # 5. Social signals
            if isinstance(results[4], tuple):
                report.social_score, social_flags = results[4]
                all_flags.extend(social_flags)
            else:
                report.social_score = 40.0

            # 6. Smart money
            if isinstance(results[5], tuple):
                report.smart_money_score, sm_flags = results[5]
                all_flags.extend(sm_flags)
            else:
                report.smart_money_score = 50.0

            # Liquidity score
            if initial_sol >= 5:
                report.liquidity_score = 80.0
            elif initial_sol >= 2:
                report.liquidity_score = 60.0
            elif initial_sol >= 0.5:
                report.liquidity_score = 40.0
            else:
                report.liquidity_score = 20.0
                all_flags.append("very_low_initial_liq")

            # DexScreener data (wait briefly for listing)
            await asyncio.sleep(3)
            dex_data = await self.dex_client.get_token_data(mint)
            if dex_data:
                market = self.dex_client.parse_market_data(dex_data)
                report.dex_volume_5m = market.get("volume_5m", 0)
                report.dex_buys_5m = market.get("buys_5m", 0)
                report.dex_sells_5m = market.get("sells_5m", 0)
                report.price_change_5m = market.get("price_change_5m", 0)
                dex_social_score, dex_flags = await self.social_analyzer.analyze_social(token_data, dex_data)
                report.social_score = max(report.social_score, dex_social_score)
                all_flags.extend(dex_flags)

            # Composite score
            report.overall_score = (
                report.rugcheck_score * self.WEIGHTS["rugcheck"] +
                report.dev_history_score * self.WEIGHTS["dev_history"] +
                report.bundle_score * self.WEIGHTS["bundle"] +
                report.holder_score * self.WEIGHTS["holder"] +
                report.liquidity_score * self.WEIGHTS["liquidity"] +
                report.social_score * self.WEIGHTS["social"] +
                report.smart_money_score * self.WEIGHTS["smart_money"]
            )

            if report.overall_score >= 75:
                report.risk_level = "SAFE"
            elif report.overall_score >= 55:
                report.risk_level = "CAUTION"
            elif report.overall_score >= 35:
                report.risk_level = "DANGER"
            else:
                report.risk_level = "RUG"

            report.flags = all_flags

            # Hard rejection rules
            hard_reject = False
            if "serial_rugger" in all_flags:
                hard_reject = True
                report.risk_level = "RUG"
            if "mint_authority_enabled" in all_flags and "freeze_authority_enabled" in all_flags:
                hard_reject = True
                report.risk_level = "RUG"
            if any("heavily_bundled" in f for f in all_flags):
                hard_reject = True
                report.risk_level = "DANGER"

            threshold = getattr(Config, 'SAFETY_SCORE_THRESHOLD', 0.70) * 100
            report.passed = (report.overall_score >= threshold) and not hard_reject

            if report.passed:
                self.tokens_passed += 1
                log.info(f"PASSED: {name} ({symbol}) | Score: {report.overall_score:.1f}/100 | "
                         f"Risk: {report.risk_level} | Flags: {', '.join(all_flags[:5])}")
            else:
                self.tokens_rejected += 1
                log.debug(f"REJECTED: {name} ({symbol}) | Score: {report.overall_score:.1f}/100 | "
                          f"Risk: {report.risk_level}")

            signal = {
                "mint": mint,
                "name": f"{name} ({symbol})",
                "entry_mcap": report.initial_mcap,
                "safety_score": report.overall_score,
                "risk_level": report.risk_level,
                "passed": report.passed,
                "flags": all_flags,
                "scores": {
                    "rugcheck": report.rugcheck_score,
                    "dev_history": report.dev_history_score,
                    "bundle": report.bundle_score,
                    "holder": report.holder_score,
                    "liquidity": report.liquidity_score,
                    "social": report.social_score,
                    "smart_money": report.smart_money_score,
                },
                "market": {
                    "volume_5m": report.dex_volume_5m,
                    "buys_5m": report.dex_buys_5m,
                    "sells_5m": report.dex_sells_5m,
                    "price_change_5m": report.price_change_5m,
                },
                "dev_wallet": dev_wallet,
                "initial_sol": initial_sol,
            }
            await self.signal_callback(signal)

        except Exception as e:
            log.error(f"Analysis pipeline error for {mint}: {e}")

    def get_stats(self):
        return {
            "tokens_seen": self.tokens_seen,
            "tokens_passed": self.tokens_passed,
            "tokens_rejected": self.tokens_rejected,
            "pass_rate": f"{self.tokens_passed / max(1, self.tokens_seen) * 100:.1f}%",
        }

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scan_new_tokens())

    async def shutdown(self):
        if self.session:
            await self.session.close()
