import time
import schedule
import os
from dotenv import load_dotenv
from scanner import get_active_markets, get_market_prices
from analyzer import analyze_market
from trader import init_client, execute_trade, close_position
from risk import RiskManager
from logger import log, send_telegram

load_dotenv()

risk = RiskManager()
clob_client = init_client()
paper_trading_mode = os.getenv("PAPER_TRADING_MODE", "False").lower() == "true"

def scan_and_trade():
    log.info("=== Starting market scan ===")
    markets = get_active_markets(min_volume=5000, limit=40)

    for market in markets:
        condition_id = market.get("conditionId")
        if not condition_id:
            continue

        # Skip if already have a position in this market
        if condition_id in risk.open_positions:
            continue

        # Fetch current prices
        prices = get_market_prices(condition_id)
        if not prices or prices.get("yes_price", 0) == 0:
            continue

        yes_price = prices["yes_price"]

        # Skip extreme prices (already near resolution)
        if yes_price < 0.03 or yes_price > 0.97:
            continue

        # Get Claude analysis
        analysis = analyze_market(market, yes_price)
        edge = analysis.get("edge", 0)
        direction = analysis.get("direction", "no_trade")
        confidence = analysis.get("confidence", "low")
        estimated_prob = analysis.get("estimated_prob", yes_price)

        if direction == "no_trade":
            continue

        # Risk check
        can_trade, reason = risk.can_trade(edge, confidence)
        if not can_trade:
            log.info(f"Cannot trade {market.get('question')[:40]}...: {reason}")
            continue

        # Calculate position size
        position_size = risk.calculate_position_size(estimated_prob, yes_price, confidence)
        if position_size == 0:
            log.info(f"Calculated position size is 0 for {market.get('question')[:40]}...")
            continue

        token_id = None
        trade_price = yes_price
        side = ""

        if direction == "buy_yes":
            token_id = prices.get("token_id_yes")
            side = "BUY"
        elif direction == "buy_no":
            token_id = prices.get("token_id_no")
            trade_price = 1 - yes_price # Price of NO token
            side = "BUY" # Always buying the token that represents our belief

        if not token_id:
            log.error(f"Could not determine token_id for {condition_id}")
            continue

        log.info(f"Attempting to {side} {position_size} of {condition_id} ({direction}) @ {trade_price}")
        trade_resp = execute_trade(clob_client, token_id, trade_price, position_size, side, paper_trading_mode)

        if trade_resp.get("success"):
            risk.record_trade_open(condition_id, direction, position_size, yes_price, token_id)
        else:
            log.error(f"Trade execution failed for {condition_id}")

def monitor_positions():
    log.info("=== Starting position monitoring ===")
    positions_to_close = []

    for condition_id, pos_data in list(risk.open_positions.items()):
        log.info(f"Monitoring position in {condition_id}")
        prices = get_market_prices(condition_id)
        if not prices or prices.get("yes_price", 0) == 0:
            log.warning(f"Could not get current prices for {condition_id}, skipping monitoring.")
            continue

        current_yes_price = prices["yes_price"]
        entry_yes_price = pos_data["entry_price"]
        direction = pos_data["direction"]
        size_usd = pos_data["size"]
        token_id = pos_data["token_id"]

        # Auto-exit logic
        should_close = False
        reason = ""

        # If market is near resolution (e.g., price > 0.95 or < 0.05) and profitable
        if (current_yes_price > 0.95 and direction == "buy_yes" and current_yes_price > entry_yes_price) or \
           (current_yes_price < 0.05 and direction == "buy_no" and current_yes_price < entry_yes_price):
            should_close = True
            reason = "Market near resolution and profitable"
        
        # If price moved significantly against position (e.g., 10% adverse movement)
        if direction == "buy_yes" and (entry_yes_price - current_yes_price) / entry_yes_price > 0.10:
            should_close = True
            reason = "Significant adverse price movement (YES)"
        elif direction == "buy_no" and (current_yes_price - entry_yes_price) / (1 - entry_yes_price) > 0.10: # Assuming entry_yes_price is the YES price when NO was bought
            should_close = True
            reason = "Significant adverse price movement (NO)"

        if should_close:
            log.info(f"Closing position in {condition_id}: {reason}")
            # For closing, we always SELL the token we hold
            current_token_price = current_yes_price if direction == "buy_yes" else (1 - current_yes_price)
            size_shares = size_usd / pos_data["entry_price"] if direction == "buy_yes" else size_usd / (1 - pos_data["entry_price"])
            
            close_resp = close_position(clob_client, token_id, current_token_price, size_shares, paper_trading_mode)
            if close_resp.get("success"):
                risk.record_trade_close(condition_id, current_yes_price)
            else:
                log.error(f"Failed to close position for {condition_id}")

def daily_report():
    report = risk.status_report()
    send_telegram(report)
    log.info("Daily report sent.")
    risk.reset_daily_stats()

def health_check():
    log.info("Bot is alive and running...")
    send_telegram("❤️ OpenClaw Bot is alive!")

# Schedule tasks
schedule.every(15).minutes.do(scan_and_trade)
schedule.every(5).minutes.do(monitor_positions)
schedule.every().day.at("23:00").do(daily_report)
schedule.every(6).hours.do(health_check)

log.info("OpenClaw Bot started. Scheduling tasks...")
send_telegram("🚀 OpenClaw Bot has started!")

try:
    while True:
        schedule.run_pending()
        time.sleep(1)
except KeyboardInterrupt:
    log.info("Bot stopped by user (KeyboardInterrupt).")
    send_telegram("🛑 OpenClaw Bot stopped.")
except Exception as e:
    log.critical(f"Unhandled exception: {e}")
    send_telegram(f"🚨 OpenClaw Bot encountered a critical error: {e}")
