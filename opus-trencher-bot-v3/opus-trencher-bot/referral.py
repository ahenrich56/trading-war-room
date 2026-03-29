from database import Database
from config import Config
from datetime import datetime, timedelta

class ReferralSystem:
    def __init__(self, db: Database):
        self.db = db

    def register_referral(self, referrer_id, referred_id):
        """Registers a new referral and awards free days."""
        if not referrer_id or referrer_id == referred_id:
            return False
        
        # Check if referral already exists
        existing_referral = self.db._get_connection().execute('SELECT id FROM referrals WHERE referred_id = ?', (referred_id,)).fetchone()
        if existing_referral:
            return False
        
        # Add to database
        self.db.add_referral(referrer_id, referred_id)
        
        # Award referred user 2 extra days
        self._award_free_days(referred_id, Config.REFERRED_FREE_DAYS)
        
        # Referrer gets 7 days free (awarded upon payment)
        return True

    def process_referral_reward(self, referred_id):
        """Awards referrer 10% commission and 7 free days when referred user pays."""
        referral = self.db._get_connection().execute('SELECT referrer_id FROM referrals WHERE referred_id = ? AND reward_paid = 0', (referred_id,)).fetchone()
        if referral:
            referrer_id = referral[0]
            
            # Award referrer 7 free days
            self._award_free_days(referrer_id, Config.REFERRAL_FREE_DAYS)
            
            # Mark reward as paid
            self.db._get_connection().execute('UPDATE referrals SET reward_paid = 1 WHERE referred_id = ?', (referred_id,))
            return True, referrer_id
        return False, None

    def _award_free_days(self, user_id, days):
        """Extends or creates membership with free days."""
        membership = self.db.get_membership(user_id)
        if membership:
            current_expiry = datetime.fromisoformat(membership[1])
            new_expiry = current_expiry + timedelta(days=days)
            self.db.update_membership(user_id, new_expiry.isoformat(), membership[2])
        else:
            new_expiry = datetime.now() + timedelta(days=days)
            self.db.update_membership(user_id, new_expiry.isoformat(), "free_trial")
