import os
from logger import log, send_telegram
import json

class RiskManager:
    def __init__(self):
        self.max_position_size = float(os.getenv("MAX_POSITION_SIZE", 200))
        self.max_open_positions = int(os.getenv("MAX_OPEN_POSITIONS", 5))
        self.min_edge = float(os.getenv("MIN_EDGE_THRESHOLD", 0.15))
        self.daily_loss_limit = float(os.getenv("DAILY_LOSS_LIMIT", 300))
        self.paper_trading_mode = os.getenv("PAPER_TRADING_MODE", "False").lower() == "true"
        self.open_positions = self._load_positions()
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.wins = 0
        self.losses = 0

    def _load_positions(self):
        if os.path.exists("open_positions.json"):
            with open("open_positions.json", "r") as f:
                return json.load(f)
        return {}

    def _save_positions(self):
        with open("open_positions.json", "w") as f:
            json.dump(self.open_positions, f, indent=4)

    def can_trade(self, edge: float, confidence: str) -> tuple[bool, str]:
        if self.daily_pnl <= -self.daily_loss_limit:
            return False, f"Daily loss limit hit: ${abs(self.daily_pnl):.2f}"

        if len(self.open_positions) >= self.max_open_positions:
            return False, f"Max open positions reached: {self.max_open_positions}"

        if edge < self.min_edge:
            return False, f"Edge too small: {edge:.2f} < {self.min_edge}"

        if confidence == "low":
            return False, "Confidence too low"

        return True, "OK"

    def calculate_position_size(self, estimated_prob: float, current_price: float, confidence: str) -> float:
        """Improved Kelly-inspired position sizing."""
        # f = (bp - q) / b  where b = 1 (payout is 1:1), p = estimated_prob, q = 1-p, b = current_price / (1-current_price)
        # For Polymarket, it's simpler: f = (edge) / (odds of losing)
        # Simplified Kelly Criterion for 1:1 payout markets (like Polymarket YES/NO)
        # f = p - q / b where p is estimated_prob, q is (1-estimated_prob), b is implied odds (current_price / (1-current_price))
        # More practically, f = (estimated_prob - current_price) / (1 - current_price) for buying YES
        # And f = (current_price - estimated_prob) / estimated_prob for buying NO

        # Let's use a fraction of Kelly for risk management
        # f = (estimated_prob - current_price) / (1 - current_price) if buying YES
        # f = (current_price - estimated_prob) / estimated_prob if buying NO

        if estimated_prob > current_price: # Buying YES
            kelly_fraction = (estimated_prob - current_price) / (1 - current_price)
        else: # Buying NO
            kelly_fraction = (current_price - estimated_prob) / estimated_prob

        # Apply a fraction of Kelly to reduce risk (e.g., 0.1 to 0.5)
        kelly_multiplier = 0.2 # Start with 20% of Kelly
        if confidence == "medium":
            kelly_multiplier = 0.3
        elif confidence == "high":
            kelly_multiplier = 0.5

        size_fraction = min(max(0, kelly_fraction * kelly_multiplier), 1.0) # Ensure between 0 and 1
        size = self.max_position_size * size_fraction

        return round(size, 2)

    def record_trade_open(self, condition_id: str, direction: str, size: float, entry_price: float, token_id: str):
        self.open_positions[condition_id] = {
            "direction": direction,
            "size": size,
            "entry_price": entry_price,
            "token_id": token_id,
            "open_time": datetime.now().isoformat()
        }
        self.trades_today += 1
        self._save_positions()
        log.info(f"Position opened: {condition_id} | {direction} | ${size} @ {entry_price}")

    def record_trade_close(self, condition_id: str, exit_price: float):
        if condition_id not in self.open_positions:
            return
        pos = self.open_positions.pop(condition_id)
        
        pnl = 0.0
        if pos["direction"] == "buy_yes":
            pnl = (exit_price - pos["entry_price"]) * pos["size"]
        elif pos["direction"] == "buy_no":
            # If we bought NO, profit when price goes down. exit_price is the YES price.
            # So if YES price goes down, NO price goes up.
            # Entry price for NO is (1 - YES_entry_price)
            # Exit price for NO is (1 - YES_exit_price)
            pnl = ((1 - exit_price) - (1 - pos["entry_price"])) * pos["size"]

        self.daily_pnl += pnl
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1

        self._save_positions()
        msg = f"✅ Trade closed: {'WIN' if pnl > 0 else '❌ LOSS'} | PnL: ${pnl:.2f} | Daily PnL: ${self.daily_pnl:.2f}"
        log.info(msg)
        send_telegram(msg)

    def status_report(self) -> str:
        win_rate = (self.wins / self.trades_today * 100) if self.trades_today > 0 else 0
        return (
            f"📊 *OpenClaw Bot Status*\n"
            f"Trades today: {self.trades_today}\n"
            f"Win rate: {win_rate:.1f}%\n"
            f"Daily PnL: ${self.daily_pnl:.2f}\n"
            f"Open positions: {len(self.open_positions)}\n"
            f"Loss limit remaining: ${self.daily_loss_limit + self.daily_pnl:.2f}"
        )

    def reset_daily_stats(self):
        self.daily_pnl = 0.0
        self.trades_today = 0
        self.wins = 0
        self.losses = 0
        log.info("Daily stats reset.")
