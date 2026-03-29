"""
Dashboard API Server — Runs alongside the bot
===============================================
Serves real-time bot stats + standalone web dashboard via HTTP.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from aiohttp import web
from config import Config
from database import Database

log = logging.getLogger("DashboardAPI")
DASHBOARD_DIR = Path(__file__).parent / "dashboard"


class DashboardAPI:
    def __init__(self, db: Database, auto_trader=None, scanner=None, whale_intel=None):
        self.db = db
        self.auto_trader = auto_trader
        self.scanner = scanner
        self.whale_intel = whale_intel
        self.app = web.Application(middlewares=[self.cors_middleware])
        self._setup_routes()

    @web.middleware
    async def cors_middleware(self, request, handler):
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            try:
                response = await handler(request)
            except web.HTTPException as ex:
                response = ex
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    def _setup_routes(self):
        self.app.router.add_get("/", self.get_index)
        self.app.router.add_get("/api/status", self.get_status)
        self.app.router.add_get("/api/signals", self.get_signals)
        self.app.router.add_get("/api/trades", self.get_trades)
        self.app.router.add_get("/api/stats", self.get_stats)
        self.app.router.add_post("/api/toggle-mode", self.toggle_mode)
        self.app.router.add_get("/api/health", self.health)
        
        # Serve dashboard folder if it exists
        if DASHBOARD_DIR.exists():
            self.app.router.add_static("/dashboard", DASHBOARD_DIR)

    async def get_index(self, request):
        """Serve the dashboard HTML."""
        index_path = DASHBOARD_DIR / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(text="Dashboard index.html not found", status=404)

    async def health(self, request):
        return web.json_response({"status": "ok", "paper_mode": Config.PAPER_TRADING_MODE})

    async def get_status(self, request):
        """Full bot status overview."""
        try:
            trader_status = self.auto_trader.get_status() if self.auto_trader else {}
            scanner_stats = self.scanner.get_stats() if self.scanner else {}
            whale_status = self.whale_intel.get_status() if self.whale_intel else {}
            signal_stats = self.db.get_signal_stats()
            trade_stats = self.db.get_trade_stats()

            # Open positions
            positions = []
            if self.auto_trader:
                for mint, pos in self.auto_trader.positions.items():
                    positions.append({
                        "mint": mint,
                        "name": pos.name,
                        "entry_price": pos.amount_sol,
                        "safety_score": pos.safety_score,
                        "entry_time": pos.entry_time,
                        "highest_price": pos.highest_price,
                        "status": pos.status,
                    })

            return web.json_response({
                "bot": {
                    "paper_mode": Config.PAPER_TRADING_MODE,
                    "auto_trader_enabled": Config.AUTO_TRADER_ENABLED,
                    "strategy": Config.STRATEGY_MODE,
                    "tp_mult": Config.TAKE_PROFIT_MULTIPLIER,
                    "sl_pct": Config.STOP_LOSS_MULTIPLIER,
                    "max_positions": Config.MAX_CONCURRENT_POSITIONS,
                },
                "trader": trader_status,
                "scanner": scanner_stats,
                "whale_intel": whale_status,
                "signal_stats": signal_stats,
                "trade_stats": trade_stats,
                "open_positions": positions,
            })
        except Exception as e:
            log.error(f"Error in get_status API: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def get_signals(self, request):
        """Recent token signals."""
        limit = int(request.query.get("limit", "50"))
        signals = self.db.get_recent_signals(limit)
        return web.json_response({"signals": signals})

    async def get_trades(self, request):
        """Recent trades."""
        limit = int(request.query.get("limit", "50"))
        trades = self.db.get_recent_trades(limit)
        return web.json_response({"trades": trades})

    async def get_stats(self, request):
        """Combined stats for dashboard cards."""
        signal_stats = self.db.get_signal_stats()
        trade_stats = self.db.get_trade_stats()
        trader_status = self.auto_trader.get_status() if self.auto_trader else {}
        return web.json_response({
            "signals": signal_stats,
            "trades": trade_stats,
            "trader": trader_status,
        })

    async def toggle_mode(self, request):
        """Toggle paper/live mode."""
        data = await request.json()
        new_mode = data.get("paper_mode", True)
        Config.PAPER_TRADING_MODE = new_mode
        if self.auto_trader:
            self.auto_trader.paper_mode = new_mode
        log.info(f"Mode toggled: paper_mode={new_mode}")
        return web.json_response({"paper_mode": new_mode})

    async def start(self, host="0.0.0.0", port=4000):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()
        log.info(f"Dashboard API running on http://{host}:{port}")
        return runner
