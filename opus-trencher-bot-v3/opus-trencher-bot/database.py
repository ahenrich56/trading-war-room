import sqlite3
import threading
import os
import asyncio
import logging
from contextlib import contextmanager

log = logging.getLogger("Database")


class Database:
    def __init__(self, db_path="opus_bot.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Thread-safe connection with WAL mode and busy timeout."""
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA wal_autocheckpoint=100")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        wallet_address TEXT UNIQUE,
                        private_key TEXT,
                        referred_by INTEGER,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS memberships (
                        user_id INTEGER PRIMARY KEY,
                        expiry_date TIMESTAMP,
                        plan_type TEXT,
                        is_active BOOLEAN DEFAULT 0,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        referrer_id INTEGER,
                        referred_id INTEGER,
                        reward_paid BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                        FOREIGN KEY (referred_id) REFERENCES users (user_id)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS signals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        token_ca TEXT,
                        token_name TEXT,
                        market_cap REAL,
                        safety_score REAL,
                        risk_level TEXT DEFAULT 'UNKNOWN',
                        passed INTEGER DEFAULT 0,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        token_ca TEXT,
                        token_name TEXT,
                        buy_price REAL,
                        sell_price REAL,
                        amount REAL,
                        pnl REAL,
                        status TEXT,
                        reason TEXT DEFAULT '',
                        paper_mode INTEGER DEFAULT 1,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id)
                    )
                ''')
                
                # Migrations: Add columns if they don't exist
                try:
                    cursor.execute("SELECT passed FROM signals LIMIT 1")
                except sqlite3.OperationalError:
                    log.info("Migration: Adding 'passed' column to 'signals' table")
                    cursor.execute("ALTER TABLE signals ADD COLUMN passed INTEGER DEFAULT 0")

                try:
                    cursor.execute("SELECT paper_mode FROM trades LIMIT 1")
                except sqlite3.OperationalError:
                    log.info("Migration: Adding 'paper_mode' column to 'trades' table")
                    cursor.execute("ALTER TABLE trades ADD COLUMN paper_mode INTEGER DEFAULT 1")
                
                conn.commit()

    def add_user(self, user_id, username, wallet_address, private_key, referred_by=None):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    'INSERT OR IGNORE INTO users (user_id, username, wallet_address, private_key, referred_by) VALUES (?, ?, ?, ?, ?)',
                    (user_id, username, wallet_address, private_key, referred_by)
                )

    def get_user(self, user_id):
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
                return dict(row) if row else None

    def update_membership(self, user_id, expiry_date, plan_type, is_active=1):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO memberships (user_id, expiry_date, plan_type, is_active) VALUES (?, ?, ?, ?)',
                    (user_id, expiry_date, plan_type, is_active)
                )

    def get_membership(self, user_id):
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute('SELECT * FROM memberships WHERE user_id = ?', (user_id,)).fetchone()
                return dict(row) if row else None

    def add_referral(self, referrer_id, referred_id):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    'INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)',
                    (referrer_id, referred_id)
                )

    def get_referral_stats(self, user_id):
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute('SELECT COUNT(*) as cnt FROM referrals WHERE referrer_id = ?', (user_id,)).fetchone()
                return row['cnt'] if row else 0

    def add_signal(self, token_ca, token_name, market_cap, safety_score, risk_level="UNKNOWN", passed=False):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    'INSERT INTO signals (token_ca, token_name, market_cap, safety_score, risk_level, passed) VALUES (?, ?, ?, ?, ?, ?)',
                    (token_ca, token_name, market_cap, safety_score, risk_level, 1 if passed else 0)
                )

    def add_trade(self, token_ca, token_name, buy_price, amount, status="OPEN", paper_mode=True, reason=""):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    'INSERT INTO trades (user_id, token_ca, token_name, buy_price, amount, status, reason, paper_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (0, token_ca, token_name, buy_price, amount, status, reason, 1 if paper_mode else 0)
                )

    def close_trade(self, token_ca, sell_price, pnl, reason=""):
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    'UPDATE trades SET sell_price=?, pnl=?, status=?, reason=? WHERE token_ca=? AND status=?',
                    (sell_price, pnl, "CLOSED", reason, token_ca, "OPEN")
                )

    # ═══ DASHBOARD API METHODS ═══

    def get_recent_signals(self, limit=50):
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    'SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?', (limit,)
                ).fetchall()
                return [dict(r) for r in rows]

    def get_recent_trades(self, limit=50):
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    'SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?', (limit,)
                ).fetchall()
                return [dict(r) for r in rows]

    def get_signal_stats(self):
        with self._lock:
            with self._get_connection() as conn:
                total = conn.execute('SELECT COUNT(*) as cnt FROM signals').fetchone()['cnt']
                passed = conn.execute('SELECT COUNT(*) as cnt FROM signals WHERE passed = 1').fetchone()['cnt']
                avg_score = conn.execute('SELECT AVG(safety_score) as avg FROM signals').fetchone()['avg'] or 0
                return {"total_scanned": total, "total_passed": passed, "avg_score": round(avg_score, 1)}

    def get_trade_stats(self):
        with self._lock:
            with self._get_connection() as conn:
                total = conn.execute('SELECT COUNT(*) as cnt FROM trades').fetchone()['cnt']
                closed = conn.execute('SELECT COUNT(*) as cnt FROM trades WHERE status = "CLOSED"').fetchone()['cnt']
                wins = conn.execute('SELECT COUNT(*) as cnt FROM trades WHERE status = "CLOSED" AND pnl > 0').fetchone()['cnt']
                losses = conn.execute('SELECT COUNT(*) as cnt FROM trades WHERE status = "CLOSED" AND pnl <= 0').fetchone()['cnt']
                total_pnl_row = conn.execute('SELECT SUM(pnl) as s FROM trades WHERE status = "CLOSED"').fetchone()
                total_pnl = total_pnl_row['s'] if total_pnl_row['s'] else 0
                open_count = conn.execute('SELECT COUNT(*) as cnt FROM trades WHERE status = "OPEN"').fetchone()['cnt']
                return {
                    "total_trades": total, "closed": closed, "open": open_count,
                    "wins": wins, "losses": losses,
                    "win_rate": round((wins / max(closed, 1)) * 100, 1),
                    "total_pnl": round(total_pnl, 4)
                }
