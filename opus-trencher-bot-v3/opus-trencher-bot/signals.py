from telegram import Bot
from config import Config
from database import Database
import logging

log = logging.getLogger("Signals")


class SignalDistributor:
    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot
        self.channel_id = Config.SIGNAL_CHANNEL_ID

    async def send_signal(self, signal_data):
        """Sends a signal to the Telegram channel for subscribed users."""
        mint = signal_data.get("mint")
        name = signal_data.get("name")
        entry_mcap = signal_data.get("entry_mcap", 0)
        safety_score = signal_data.get("safety_score", 0)

        # Log signal to database using thread-safe method
        try:
            self.db.add_signal(mint, name, entry_mcap, safety_score)
        except Exception as e:
            log.debug(f"DB signal log error: {e}")

        # Message for Telegram channel
        signal_message = (
            f"🚀 *NEW SIGNAL DETECTED* 🚀\n\n"
            f"*Token:* {name}\n"
            f"*CA:* `{mint}`\n"
            f"*Entry Market Cap:* ${entry_mcap:,.0f}\n"
            f"*Safety Score:* {safety_score:.1f}/100\n\n"
            f"🔗 [View on pump.fun](https://pump.fun/{mint})"
        )

        if self.channel_id:
            try:
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=signal_message,
                    parse_mode="Markdown"
                )
            except Exception as e:
                log.debug(f"Channel send error: {e}")

        log.info(f"Signal: {name} ({mint[:12]}...) | Score: {safety_score:.1f} | MCap: ${entry_mcap:,.0f}")
