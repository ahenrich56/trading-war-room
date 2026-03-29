import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # === CORE CREDENTIALS ===
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    TREASURY_WALLET_ADDRESS = os.getenv("TREASURY_WALLET_ADDRESS", "YOUR_TREASURY_WALLET")
    SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    PUMPPORTAL_API_KEY = os.getenv("PUMPPORTAL_API_KEY", "")
    RUGCHECK_API_KEY = os.getenv("RUGCHECK_API_KEY", "")
    HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")

    # === ADMIN ===
    ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "6356489578").split(",") if x.strip()]

    # === SUBSCRIPTION PRICES (SOL only) ===
    WEEKLY_SOL_PRICE = float(os.getenv("WEEKLY_SOL_PRICE", "0.5"))
    MONTHLY_SOL_PRICE = float(os.getenv("MONTHLY_SOL_PRICE", "1.5"))
    LIFETIME_SOL_PRICE = float(os.getenv("LIFETIME_SOL_PRICE", "5.0"))

    # === REFERRAL REWARDS ===
    REFERRAL_REWARD_PERCENT = 0.10
    REFERRAL_FREE_DAYS = 7
    REFERRED_FREE_DAYS = 2

    # === BOT SETTINGS ===
    SIGNAL_CHANNEL_ID = os.getenv("SIGNAL_CHANNEL_ID", "")
    AUTO_TRADER_ENABLED = os.getenv("AUTO_TRADER_ENABLED", "True").lower() == "true"
    PAPER_TRADING_MODE = os.getenv("PAPER_TRADING_MODE", "True").lower() == "true"

    # === SCANNER SETTINGS (v2.0) ===
    SAFETY_SCORE_THRESHOLD = float(os.getenv("SAFETY_SCORE_THRESHOLD", "0.70"))
    MIN_INITIAL_LIQUIDITY_SOL = float(os.getenv("MIN_INITIAL_LIQUIDITY_SOL", "0.5"))

    # Scanner weight overrides (must sum to 1.0)
    SCANNER_WEIGHT_RUGCHECK = float(os.getenv("SCANNER_WEIGHT_RUGCHECK", "0.25"))
    SCANNER_WEIGHT_DEV = float(os.getenv("SCANNER_WEIGHT_DEV", "0.20"))
    SCANNER_WEIGHT_BUNDLE = float(os.getenv("SCANNER_WEIGHT_BUNDLE", "0.15"))
    SCANNER_WEIGHT_HOLDER = float(os.getenv("SCANNER_WEIGHT_HOLDER", "0.10"))
    SCANNER_WEIGHT_LIQUIDITY = float(os.getenv("SCANNER_WEIGHT_LIQUIDITY", "0.10"))
    SCANNER_WEIGHT_SOCIAL = float(os.getenv("SCANNER_WEIGHT_SOCIAL", "0.10"))
    SCANNER_WEIGHT_SMART_MONEY = float(os.getenv("SCANNER_WEIGHT_SMART_MONEY", "0.10"))

    # === TRADING SETTINGS (Aggressive $10->$1K Strategy) ===
    STRATEGY_MODE = os.getenv("STRATEGY_MODE", "aggressive")
    BANKROLL_PCT = float(os.getenv("BANKROLL_PCT", "0.10"))
    TAKE_PROFIT_MULTIPLIER = float(os.getenv("TAKE_PROFIT_MULT", "3.0"))
    STOP_LOSS_MULTIPLIER = float(os.getenv("STOP_LOSS_PCT", "0.40"))
    TRADES_PER_DAY = int(os.getenv("TRADES_PER_DAY", "8"))
    COMPOUNDING_MODE = os.getenv("COMPOUNDING_MODE", "full")
    MAX_CONCURRENT_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", "3"))
    DEFAULT_BUY_AMOUNT_SOL = float(os.getenv("DEFAULT_BUY_AMOUNT_SOL", "0.1"))

    # === RISK MANAGEMENT ===
    DAILY_LOSS_LIMIT_SOL = float(os.getenv("DAILY_LOSS_LIMIT", "5.0"))
    MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", "0.35"))

    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS
