# OPUS The Trencher Bot Replica

A complete Telegram bot system replicating the OPUS The Trencher platform for pump.fun memecoin signals and autotrading on Solana.

## Features

- **Telegram Bot**: Commands for wallet creation, balance checks, payment processing, membership status, and referrals.
- **Subscription System**: Biweekly and Monthly plans paid in OPUS tokens and SOL.
- **Referral Program**: Multi-tier referral system with commission and free access rewards.
- **Signal Scanner**: Real-time pump.fun token scanner with safety scoring and distribution.
- **Autotrading Bot**: Automated trading via PumpPortal Lightning API with TP/SL tracking.
- **Database**: SQLite database for users, memberships, referrals, signals, and trades.

## Project Structure

```
opus-trencher-bot/
├── .env                  # Credentials and configuration placeholders
├── requirements.txt      # Project dependencies
├── main.py               # Entry point, starts all components
├── telegram_bot.py       # Telegram bot handlers
├── wallet_manager.py     # Solana wallet creation & management
├── payment_processor.py  # Subscription payment handling
├── membership.py         # Membership tracking & expiry
├── referral.py           # Referral system
├── scanner.py            # pump.fun token scanner
├── auto_trader.py        # Automated trading bot
├── signals.py            # Signal generation & distribution
├── database.py           # SQLite database models
├── config.py             # Configuration loader
└── README.md             # Setup instructions
```

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**:
   Edit the `.env` file and provide your credentials:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather.
   - `TREASURY_WALLET_ADDRESS`: Your Solana treasury wallet address to receive payments.
   - `SOLANA_RPC_URL`: Your Solana RPC endpoint.
   - `PUMPPORTAL_API_KEY`: Your PumpPortal API key for trading and data streaming.
   - `SIGNAL_CHANNEL_ID`: The ID of the Telegram channel to send signals to.

3. **Run the Bot**:
   ```bash
   python main.py
   ```

## Disclaimer

This project is a replica of the OPUS The Trencher system for educational and development purposes. Ensure you comply with all local regulations regarding cryptocurrency trading and bot usage.
