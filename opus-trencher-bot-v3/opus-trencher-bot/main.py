"""
OPUS Trencher Bot — Main Entry Point
======================================
Orchestrates: Scanner → Signals → AutoTrader → Telegram Bot
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone
from config import Config
from database import Database
from telegram_bot import TelegramBot
from scanner import TokenScanner
from signals import SignalDistributor
from auto_trader import AutoTrader
from whale_intelligence import WhaleIntelligence
from dashboard_api import DashboardAPI

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("Main")


class BotOrchestrator:
    """Coordinates all bot components."""

    def __init__(self):
        self.db = Database()
        self.auto_trader = AutoTrader(self.db)
        self.whale_intel = WhaleIntelligence()
        self.bot_handler = TelegramBot(self.db)
        self.bot_app = None
        self.signal_distributor = None
        self.scanner = None
        self.dashboard_api = None
        self._dashboard_runner = None
        self._shutdown_event = asyncio.Event()

    async def signal_router(self, signal_data: dict):
        """
        Routes scanner signals to both:
        1. Signal distributor (Telegram alerts to subscribers)
        2. Auto trader (for automated trading)
        """
        try:
            # Send to Telegram subscribers
            if self.signal_distributor:
                try:
                    await self.signal_distributor.send_signal(signal_data)
                except Exception as e:
                    log.debug(f"Signal distributor error: {e}")

            # Send to auto trader
            if Config.AUTO_TRADER_ENABLED:
                try:
                    await self.auto_trader.on_signal(signal_data)
                except Exception as e:
                    log.debug(f"Auto trader signal error: {e}")

            # Feed to whale intelligence for pattern detection
            try:
                await self.whale_intel.on_scanner_token(signal_data)
            except Exception as e:
                log.debug(f"Whale intel signal error: {e}")

        except Exception as e:
            log.error(f"Signal routing error: {e}")

    async def daily_reset_loop(self):
        """Resets daily counters at midnight UTC."""
        while not self._shutdown_event.is_set():
            try:
                now = datetime.now(timezone.utc)
                # Calculate seconds until next midnight
                tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
                if now.hour >= 0:
                    from datetime import timedelta
                    tomorrow = tomorrow + timedelta(days=1)
                wait_seconds = (tomorrow - now).total_seconds()
                await asyncio.sleep(min(wait_seconds, 3600))

                if datetime.now(timezone.utc).hour == 0:
                    self.auto_trader.reset_daily()
                    log.info("Daily reset complete")
            except Exception as e:
                log.error(f"Daily reset error: {e}")
                await asyncio.sleep(60)

    async def status_report_loop(self):
        """Logs status every 15 minutes."""
        while not self._shutdown_event.is_set():
            await asyncio.sleep(900)  # 15 minutes
            try:
                scanner_stats = self.scanner.get_stats() if self.scanner else {}
                trader_status = self.auto_trader.get_status()
                whale_status = self.whale_intel.get_status()
                log.info(f"Scanner: {scanner_stats}")
                log.info(f"Trader: {trader_status}")
                log.info(f"Whale Intel: {whale_status}")
            except Exception as e:
                log.error(f"Status report error: {e}")

    async def run(self):
        """Main entry point — starts all components."""
        log.info("=" * 50)
        log.info("  OPUS Trencher Bot Starting...")
        log.info(f"  Paper Mode: {Config.PAPER_TRADING_MODE}")
        log.info(f"  Auto Trader: {Config.AUTO_TRADER_ENABLED}")
        log.info(f"  Strategy: {Config.STRATEGY_MODE}")
        log.info(f"  TP: {Config.TAKE_PROFIT_MULTIPLIER}x | SL: {Config.STOP_LOSS_MULTIPLIER*100}%")
        log.info(f"  Max Positions: {Config.MAX_CONCURRENT_POSITIONS}")
        log.info(f"  Scanner Threshold: {Config.SAFETY_SCORE_THRESHOLD*100}%")
        log.info(f"  Whale Intelligence: ENABLED")
        log.info("=" * 50)

        # Initialize Telegram bot application
        self.bot_app = self.bot_handler.run()
        self.signal_distributor = SignalDistributor(self.db, self.bot_app.bot)

        # Initialize scanner with signal router
        self.scanner = TokenScanner(self.db, self.signal_router)

        # Give telegram bot access to auto_trader and whale_intel for status commands
        self.bot_handler.auto_trader = self.auto_trader
        self.bot_handler.whale_intel = self.whale_intel

        # Initialize auto trader
        await self.auto_trader.init()

        # Initialize whale intelligence
        await self.whale_intel.init()
        self.whale_intel.set_signal_callback(self.signal_router)

        # Start Dashboard REST API on port 8420
        self.dashboard_api = DashboardAPI(
            db=self.db,
            auto_trader=self.auto_trader,
            scanner=self.scanner,
            whale_intel=self.whale_intel,
        )
        self._dashboard_runner = await self.dashboard_api.start(port=4000)

        # Start Telegram bot using async methods (not run_polling which blocks)
        log.info("Starting Telegram Bot...")
        try:
            await self.bot_app.initialize()
            await self.bot_app.start()
            await self.bot_app.updater.start_polling(drop_pending_updates=True)
            log.info("Telegram Bot started successfully")
        except Exception as e:
            log.error(f"Telegram bot startup error: {e}")

        # Start auto trader position monitor
        if Config.AUTO_TRADER_ENABLED:
            log.info("Starting Auto Trader monitor...")
            self.auto_trader.run()

        # Start whale intelligence monitoring
        log.info("Starting Whale Intelligence...")
        asyncio.create_task(self.whale_intel.run())

        # Start background tasks
        asyncio.create_task(self.daily_reset_loop())
        asyncio.create_task(self.status_report_loop())

        # Start scanner (main blocking loop)
        log.info("Starting Token Scanner...")
        try:
            await self.scanner.scan_new_tokens()
        except KeyboardInterrupt:
            log.info("Shutdown requested by user")
        except Exception as e:
            log.error(f"Scanner fatal error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown."""
        log.info("Shutting down...")
        self._shutdown_event.set()
        await self.auto_trader.shutdown()
        await self.whale_intel.shutdown()
        if self.scanner:
            await self.scanner.shutdown()
        # Stop telegram bot gracefully
        if self.bot_app:
            try:
                await self.bot_app.updater.stop()
                await self.bot_app.stop()
                await self.bot_app.shutdown()
            except Exception as e:
                log.debug(f"Telegram shutdown: {e}")
        log.info("Shutdown complete")


def handle_signal(signum, frame):
    log.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    orchestrator = BotOrchestrator()
    asyncio.run(orchestrator.run())
