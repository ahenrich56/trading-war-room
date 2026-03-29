from database import Database
from datetime import datetime

class MembershipSystem:
    def __init__(self, db: Database):
        self.db = db

    def is_active(self, user_id):
        """Checks if a user's membership is active and not expired."""
        membership = self.db.get_membership(user_id)
        if not membership:
            return False
        
        expiry_date = datetime.fromisoformat(membership[1])
        if datetime.now() < expiry_date:
            return True
        
        # Auto-expire access
        self.db.update_membership(user_id, membership[1], membership[2], is_active=0)
        return False

    def get_status(self, user_id):
        """Returns the status and expiry date of a user's membership."""
        membership = self.db.get_membership(user_id)
        if not membership:
            return "INACTIVE", None
        
        expiry_date = datetime.fromisoformat(membership[1])
        if datetime.now() < expiry_date:
            return "ACTIVE", expiry_date
        
        return "EXPIRED", expiry_date
