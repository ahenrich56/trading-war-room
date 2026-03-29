"""
Telegram Bot v3.0 — Admin system, SOL-only payments, paper trading controls
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import Config
from database import Database
from wallet_manager import WalletManager
from payment_processor import PaymentProcessor
from datetime import datetime
import logging

log = logging.getLogger("TelegramBot")


class TelegramBot:
    def __init__(self, db: Database):
        self.db = db
        self.payment_processor = PaymentProcessor(db)
        self.auto_trader = None
        self.whale_intel = None

    def _is_admin(self, user_id: int) -> bool:
        return Config.is_admin(user_id)

    def _get_main_keyboard(self, user_id: int):
        """Build main menu keyboard. Admins get extra buttons."""
        keyboard = [
            [InlineKeyboardButton("💰 CHECK BALANCE", callback_data="check_balance")],
            [InlineKeyboardButton("🔑 SUBSCRIBE", callback_data="pay_now")],
            [InlineKeyboardButton("📊 MEMBERSHIP STATUS", callback_data="membership_status")],
            [InlineKeyboardButton("🐋 WHALE ALERTS", callback_data="whale_alerts"),
             InlineKeyboardButton("📈 BOT STATUS", callback_data="bot_status")],
            [InlineKeyboardButton("👥 MY REFERRALS", callback_data="my_referrals")],
            [InlineKeyboardButton("❓ HOW IT WORKS", callback_data="help")]
        ]
        if self._is_admin(user_id):
            keyboard.append([
                InlineKeyboardButton("⚙️ ADMIN PANEL", callback_data="admin_panel")
            ])
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or "Trader"

        # Handle referral links: /start <referrer_id>
        referrer_id = None
        if context.args and context.args[0].isdigit():
            referrer_id = int(context.args[0])
            if referrer_id == user_id:
                referrer_id = None

        user = self.db.get_user(user_id)
        if not user:
            address, private_key = WalletManager.generate_wallet()
            self.db.add_user(user_id, username, address, private_key, referred_by=referrer_id)
            if referrer_id:
                self.db.add_referral(referrer_id, user_id)
            user = self.db.get_user(user_id)

        address = user[2]
        is_admin = self._is_admin(user_id)

        if is_admin:
            welcome_text = (
                f"👑 *Welcome back, Admin {username}!*\n\n"
                f"Your wallet:\n`{address}`\n\n"
                "You have full access to all features.\n"
                "Use the Admin Panel to control paper/live trading, "
                "view detailed stats, and manage the bot."
            )
        else:
            welcome_text = (
                f"🐋 *Welcome to Trencher Bot, {username}!*\n\n"
                f"Your personal Solana deposit wallet:\n`{address}`\n\n"
                "Deposit SOL to this address to subscribe and access:\n"
                "• Real-time pump.fun token signals\n"
                "• AI-powered auto trading\n"
                "• Whale Intelligence & smart money tracking\n\n"
                "Tap SUBSCRIBE to choose a plan!"
            )

        reply_markup = self._get_main_keyboard(user_id)
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "🐋 *Trencher Bot — How It Works*\n\n"
            "*STEP 1:* Press /start to create your deposit wallet.\n"
            "*STEP 2:* Send SOL to your wallet address.\n"
            "*STEP 3:* Tap SUBSCRIBE and choose a plan.\n"
            "*STEP 4:* Get real-time signals & auto trading!\n\n"
            "*PRICING (SOL only):*\n"
            f"• Weekly: {Config.WEEKLY_SOL_PRICE} SOL — 7 days\n"
            f"• Monthly: {Config.MONTHLY_SOL_PRICE} SOL — 30 days (BEST VALUE)\n"
            f"• Lifetime: {Config.LIFETIME_SOL_PRICE} SOL — Forever\n"
            f"+ ~0.01 SOL for transaction fees\n\n"
            "*COMMANDS:*\n"
            "/start — Main menu\n"
            "/whale — Recent whale alerts\n"
            "/status — Bot & trading status\n"
            "/help — This message\n\n"
            "*REFERRALS:*\n"
            "Share your link and earn 10% + 7 free days!\n"
            "Your friend gets 2 extra days."
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def whale_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if self.whale_intel:
            text = self.whale_intel.get_recent_alerts_formatted(limit=10)
        else:
            text = "🐋 Whale Intelligence is initializing..."
        await update.message.reply_text(text, parse_mode="Markdown")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        lines = ["📊 *Bot Status Report*\n"]
        if self.auto_trader:
            s = self.auto_trader.get_status()
            mode = "📝 PAPER" if s.get('paper_mode') else "🔴 LIVE"
            lines.append(f"*Mode:* {mode}")
            lines.append(f"*Bankroll:* {s.get('bankroll', 'N/A')}")
            lines.append(f"*Total PnL:* {s.get('total_pnl', 'N/A')}")
            lines.append(f"*Daily PnL:* {s.get('daily_pnl', 'N/A')}")
            lines.append(f"*Trades:* {s.get('total_trades', 0)} (W:{s.get('wins', 0)} L:{s.get('losses', 0)})")
            lines.append(f"*Win Rate:* {s.get('win_rate', 'N/A')}")
            lines.append(f"*Open Positions:* {s.get('open_positions', 0)}")
            lines.append(f"*Max Drawdown:* {s.get('max_drawdown', 'N/A')}")
        if self.whale_intel:
            w = self.whale_intel.get_status()
            lines.append(f"\n🐋 *Whale Intel:*")
            lines.append(f"Tracked Whales: {w.get('tracked_whales', 0)}")
            lines.append(f"Alerts (1h): {w.get('alerts_1h', 0)}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        user = self.db.get_user(user_id)

        if query.data == "check_balance":
            address = user[2]
            sol, _ = WalletManager.get_balance(address)
            await query.edit_message_text(
                f"💰 *Wallet Balance:*\n\nSOL: {sol:.4f}\nAddress: `{address}`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="check_balance"),
                     InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                ]), parse_mode="Markdown")

        elif query.data == "pay_now":
            keyboard = [
                [InlineKeyboardButton(f"Weekly ({Config.WEEKLY_SOL_PRICE} SOL — 7 days)", callback_data="pay_weekly")],
                [InlineKeyboardButton(f"Monthly ({Config.MONTHLY_SOL_PRICE} SOL — 30 days) ⭐", callback_data="pay_monthly")],
                [InlineKeyboardButton(f"Lifetime ({Config.LIFETIME_SOL_PRICE} SOL — Forever)", callback_data="pay_lifetime")],
                [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
            ]
            await query.edit_message_text(
                "🔑 *Choose Your Plan:*\n\n"
                "All plans include:\n"
                "• Real-time pump.fun signals\n"
                "• AI auto trader access\n"
                "• Whale Intelligence alerts\n"
                "• Smart money tracking\n\n"
                "Deposit SOL to your wallet first, then select a plan.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown")

        elif query.data.startswith("pay_"):
            plan = query.data.replace("pay_", "")
            # Admins bypass payment
            if self._is_admin(user_id):
                from datetime import timedelta
                days = {"weekly": 7, "monthly": 30, "lifetime": 36500}.get(plan, 30)
                expiry = datetime.now() + timedelta(days=days)
                self.db.update_membership(user_id, expiry.isoformat(), plan)
                await query.edit_message_text(
                    f"👑 *Admin Access Activated*\n\n"
                    f"Plan: {plan.title()}\n"
                    f"Expires: {'Never' if plan == 'lifetime' else expiry.strftime('%Y-%m-%d')}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                    ]), parse_mode="Markdown")
            else:
                success, message = self.payment_processor.process_payment(user_id, plan)
                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                    ]), parse_mode="Markdown")

        elif query.data == "membership_status":
            # Admins always active
            if self._is_admin(user_id):
                status = "👑 *Status: ADMIN (Permanent Access)*"
            else:
                membership = self.db.get_membership(user_id)
                if membership and membership[3]:
                    try:
                        expiry = datetime.fromisoformat(membership[1])
                        if expiry > datetime.now():
                            remaining = (expiry - datetime.now()).days
                            status = (
                                f"✅ *Status: ACTIVE*\n"
                                f"Plan: {membership[2].title()}\n"
                                f"Expires: {expiry.strftime('%Y-%m-%d %H:%M')}\n"
                                f"Days remaining: {remaining}"
                            )
                        else:
                            status = "❌ *Status: EXPIRED*\nRenew to continue receiving signals."
                    except Exception:
                        status = "❌ *Status: INACTIVE*"
                else:
                    status = "❌ *Status: INACTIVE*\nSubscribe to access signals and auto trading."
            await query.edit_message_text(
                status,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 RENEW", callback_data="pay_now"),
                     InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                ]), parse_mode="Markdown")

        elif query.data == "my_referrals":
            count = self.db.get_referral_stats(user_id)
            bot_me = await context.bot.get_me()
            ref_link = f"https://t.me/{bot_me.username}?start={user_id}"
            text = (
                f"👥 *Referral Program*\n\n"
                f"Your Referrals: {count}\n\n"
                f"Your Link:\n`{ref_link}`\n\n"
                f"*You get:* 10% of their payment + {Config.REFERRAL_FREE_DAYS} free days\n"
                f"*They get:* {Config.REFERRED_FREE_DAYS} extra days of access"
            )
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                ]), parse_mode="Markdown")

        elif query.data == "whale_alerts":
            if self.whale_intel:
                text = self.whale_intel.get_recent_alerts_formatted(limit=8)
            else:
                text = "🐋 Whale Intelligence is initializing..."
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="whale_alerts"),
                     InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                ]), parse_mode="Markdown")

        elif query.data == "bot_status":
            lines = ["📊 *Bot Status*\n"]
            if self.auto_trader:
                s = self.auto_trader.get_status()
                mode = "📝 PAPER" if s.get('paper_mode') else "🔴 LIVE"
                lines.append(f"Mode: {mode}")
                lines.append(f"Bankroll: {s.get('bankroll', 'N/A')}")
                lines.append(f"PnL: {s.get('total_pnl', 'N/A')}")
                lines.append(f"Trades: {s.get('total_trades', 0)} | WR: {s.get('win_rate', 'N/A')}")
                lines.append(f"Open: {s.get('open_positions', 0)}")
            if self.whale_intel:
                w = self.whale_intel.get_status()
                lines.append(f"\n🐋 Whales: {w.get('tracked_whales', 0)}")
                lines.append(f"Alerts (1h): {w.get('alerts_1h', 0)}")
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="bot_status"),
                     InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                ]), parse_mode="Markdown")

        elif query.data == "help":
            help_text = (
                "🐋 *HOW IT WORKS:*\n\n"
                "1. Deposit SOL to your wallet\n"
                "2. Select a plan via SUBSCRIBE\n"
                "3. Get real-time pump.fun signals\n"
                "4. Auto trader executes for you\n"
                "5. Whale Intel tracks smart money\n\n"
                "*Plans (SOL only):*\n"
                f"• Weekly: {Config.WEEKLY_SOL_PRICE} SOL (7 days)\n"
                f"• Monthly: {Config.MONTHLY_SOL_PRICE} SOL (30 days)\n"
                f"• Lifetime: {Config.LIFETIME_SOL_PRICE} SOL (forever)"
            )
            await query.edit_message_text(
                help_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
                ]), parse_mode="Markdown")

        # ==================== ADMIN PANEL ====================
        elif query.data == "admin_panel":
            if not self._is_admin(user_id):
                await query.edit_message_text("⛔ Access denied.")
                return
            paper = Config.PAPER_TRADING_MODE
            mode_text = "📝 PAPER MODE" if paper else "🔴 LIVE MODE"
            text = (
                f"⚙️ *Admin Control Panel*\n\n"
                f"Current Mode: {mode_text}\n"
                f"Auto Trader: {'ON' if Config.AUTO_TRADER_ENABLED else 'OFF'}\n"
                f"Scanner Threshold: {Config.SAFETY_SCORE_THRESHOLD*100:.0f}%\n"
                f"TP: {Config.TAKE_PROFIT_MULTIPLIER}x | SL: {Config.STOP_LOSS_MULTIPLIER*100:.0f}%\n"
                f"Max Positions: {Config.MAX_CONCURRENT_POSITIONS}"
            )
            toggle_text = "🔴 Switch to LIVE" if paper else "📝 Switch to PAPER"
            keyboard = [
                [InlineKeyboardButton(toggle_text, callback_data="admin_toggle_mode")],
                [InlineKeyboardButton("📊 Detailed Stats", callback_data="admin_stats")],
                [InlineKeyboardButton("📜 Recent Trades", callback_data="admin_trades")],
                [InlineKeyboardButton("🐋 Whale Status", callback_data="admin_whale")],
                [InlineKeyboardButton("🔄 Reset Daily PnL", callback_data="admin_reset_daily")],
                [InlineKeyboardButton("⬅️ BACK", callback_data="back_to_main")]
            ]
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown")

        elif query.data == "admin_toggle_mode":
            if not self._is_admin(user_id):
                return
            Config.PAPER_TRADING_MODE = not Config.PAPER_TRADING_MODE
            if self.auto_trader:
                self.auto_trader.paper_mode = Config.PAPER_TRADING_MODE
            new_mode = "📝 PAPER" if Config.PAPER_TRADING_MODE else "🔴 LIVE"
            await query.edit_message_text(
                f"✅ Switched to {new_mode} mode.\n\n"
                f"{'Trades will be simulated.' if Config.PAPER_TRADING_MODE else '⚠️ REAL TRADES will execute! Make sure your wallet is funded.'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
                ]), parse_mode="Markdown")

        elif query.data == "admin_stats":
            if not self._is_admin(user_id):
                return
            lines = ["📊 *Detailed Trading Stats*\n"]
            if self.auto_trader:
                s = self.auto_trader.get_status()
                mode = "📝 PAPER" if s.get('paper_mode') else "🔴 LIVE"
                lines.append(f"Mode: {mode}")
                lines.append(f"Starting Bankroll: {Config.DEFAULT_BUY_AMOUNT_SOL} SOL")
                lines.append(f"Current Bankroll: {s.get('bankroll', 'N/A')}")
                lines.append(f"Total PnL: {s.get('total_pnl', 'N/A')}")
                lines.append(f"Daily PnL: {s.get('daily_pnl', 'N/A')}")
                lines.append(f"Total Trades: {s.get('total_trades', 0)}")
                lines.append(f"Wins: {s.get('wins', 0)}")
                lines.append(f"Losses: {s.get('losses', 0)}")
                lines.append(f"Win Rate: {s.get('win_rate', 'N/A')}")
                lines.append(f"Open Positions: {s.get('open_positions', 0)}")
                lines.append(f"Max Drawdown: {s.get('max_drawdown', 'N/A')}")
                lines.append(f"\nStrategy: {Config.STRATEGY_MODE}")
                lines.append(f"TP: {Config.TAKE_PROFIT_MULTIPLIER}x")
                lines.append(f"SL: {Config.STOP_LOSS_MULTIPLIER*100:.0f}%")
                lines.append(f"Risk/Trade: {Config.BANKROLL_PCT*100:.0f}%")
            else:
                lines.append("Auto trader not initialized.")
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="admin_stats"),
                     InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
                ]), parse_mode="Markdown")

        elif query.data == "admin_trades":
            if not self._is_admin(user_id):
                return
            lines = ["📜 *Recent Trades*\n"]
            if self.auto_trader and hasattr(self.auto_trader, 'trade_history'):
                recent = self.auto_trader.trade_history[-10:] if self.auto_trader.trade_history else []
                if recent:
                    for t in reversed(recent):
                        emoji = "✅" if t.get('pnl', 0) > 0 else "❌"
                        lines.append(
                            f"{emoji} {t.get('name', 'Unknown')[:15]}\n"
                            f"   PnL: {t.get('pnl', 0):.4f} SOL | "
                            f"{t.get('multiplier', 0):.1f}x"
                        )
                else:
                    lines.append("No trades yet.")
            else:
                lines.append("No trade history available.")
            await query.edit_message_text(
                "\n".join(lines),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="admin_trades"),
                     InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
                ]), parse_mode="Markdown")

        elif query.data == "admin_whale":
            if not self._is_admin(user_id):
                return
            if self.whale_intel:
                w = self.whale_intel.get_status()
                text = (
                    f"🐋 *Whale Intelligence Status*\n\n"
                    f"Tracked Whales: {w.get('tracked_whales', 0)}\n"
                    f"Alerts (1h): {w.get('alerts_1h', 0)}\n"
                    f"Actionable (1h): {w.get('actionable_1h', 0)}\n"
                    f"Total Alerts: {w.get('total_alerts', 0)}\n\n"
                )
                alerts = self.whale_intel.get_recent_alerts_formatted(limit=5)
                text += alerts
            else:
                text = "Whale Intelligence not initialized."
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 REFRESH", callback_data="admin_whale"),
                     InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
                ]), parse_mode="Markdown")

        elif query.data == "admin_reset_daily":
            if not self._is_admin(user_id):
                return
            if self.auto_trader:
                self.auto_trader.reset_daily()
            await query.edit_message_text(
                "✅ Daily PnL and trade counters have been reset.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
                ]), parse_mode="Markdown")

        elif query.data == "back_to_main":
            address = user[2] if user else "Unknown"
            is_admin = self._is_admin(user_id)
            if is_admin:
                welcome_text = (
                    f"👑 *Admin Dashboard*\n\n"
                    f"Wallet: `{address}`\n\n"
                    "Full access enabled. Use Admin Panel for trading controls."
                )
            else:
                welcome_text = (
                    f"Your wallet:\n`{address}`\n\n"
                    "Deposit SOL to subscribe and start trading."
                )
            await query.edit_message_text(
                welcome_text,
                reply_markup=self._get_main_keyboard(user_id),
                parse_mode="Markdown")

    def run(self):
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("whale", self.whale_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        return application
