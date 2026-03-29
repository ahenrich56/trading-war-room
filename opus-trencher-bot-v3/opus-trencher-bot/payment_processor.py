from config import Config
from wallet_manager import WalletManager
from database import Database
from datetime import datetime, timedelta


class PaymentProcessor:
    def __init__(self, db: Database):
        self.db = db

    def process_payment(self, user_id, plan_type):
        """Checks SOL balance and transfers funds to treasury."""
        user = self.db.get_user(user_id)
        if not user:
            return False, "User not found."

        address = user[2]
        private_key = user[3]

        sol_balance, _ = WalletManager.get_balance(address)

        if plan_type == "weekly":
            required = Config.WEEKLY_SOL_PRICE
            days = 7
            label = "Weekly"
        elif plan_type == "monthly":
            required = Config.MONTHLY_SOL_PRICE
            days = 30
            label = "Monthly"
        elif plan_type == "lifetime":
            required = Config.LIFETIME_SOL_PRICE
            days = 36500  # ~100 years
            label = "Lifetime"
        else:
            return False, "Invalid plan type."

        # Need extra for tx fees
        if sol_balance < required + 0.01:
            return False, (
                f"Insufficient SOL. Required: {required} SOL + ~0.01 SOL for fees.\n"
                f"Your balance: {sol_balance:.4f} SOL"
            )

        # Transfer SOL to treasury
        success, tx_sig = WalletManager.transfer_funds(
            private_key, Config.TREASURY_WALLET_ADDRESS, amount_sol=required
        )

        if success:
            # Check if existing membership to extend
            existing = self.db.get_membership(user_id)
            if existing and existing[3] and existing[1]:
                try:
                    current_expiry = datetime.fromisoformat(existing[1])
                    if current_expiry > datetime.now():
                        expiry_date = current_expiry + timedelta(days=days)
                    else:
                        expiry_date = datetime.now() + timedelta(days=days)
                except Exception:
                    expiry_date = datetime.now() + timedelta(days=days)
            else:
                expiry_date = datetime.now() + timedelta(days=days)

            self.db.update_membership(user_id, expiry_date.isoformat(), plan_type)

            # Process referral reward if applicable
            if user[4]:  # referred_by field
                self._process_referral_reward(user[4], user_id)

            return True, (
                f"✅ {label} subscription activated!\n"
                f"Expires: {expiry_date.strftime('%Y-%m-%d %H:%M')}\n"
                f"TX: {tx_sig[:20]}..."
            )
        else:
            return False, f"Transfer failed: {tx_sig}"

    def _process_referral_reward(self, referrer_id, referred_id):
        """Give referrer bonus days."""
        try:
            existing = self.db.get_membership(referrer_id)
            if existing and existing[3]:
                current_expiry = datetime.fromisoformat(existing[1])
                new_expiry = current_expiry + timedelta(days=Config.REFERRAL_FREE_DAYS)
                self.db.update_membership(referrer_id, new_expiry.isoformat(), existing[2])
        except Exception:
            pass
