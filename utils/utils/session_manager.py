import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SessionManager:
    """Manage user sessions and preference storage"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.session_expiry = 3600  # 1 hour in seconds
    
    def store_preferences(self, session_id: str, preferences: Dict[str, Any]) -> bool:
        """Store user preferences in Redis"""
        try:
            if not self.redis_client:
                logger.warning("Redis not available, using in-memory storage")
                return False
            
            # Add timestamp
            preferences['stored_at'] = datetime.utcnow().isoformat()
            
            # Store in Redis with expiration
            key = f"preferences:{session_id}"
            self.redis_client.setex(
                key,
                self.session_expiry,
                json.dumps(preferences)
            )
            
            logger.info(f"Preferences stored for session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing preferences: {e}")
            return False
    
    def get_preferences(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user preferences from Redis"""
        try:
            if not self.redis_client:
                logger.warning("Redis not available")
                return None
            
            key = f"preferences:{session_id}"
            stored_data = self.redis_client.get(key)
            
            if stored_data:
                preferences = json.loads(stored_data)
                logger.info(f"Preferences retrieved for session: {session_id}")
                return preferences
            
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving preferences: {e}")
            return None
    
    def update_preferences(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing preferences"""
        try:
            existing_prefs = self.get_preferences(session_id)
            if not existing_prefs:
                return False
            
            # Merge updates
            existing_prefs.update(updates)
            existing_prefs['updated_at'] = datetime.utcnow().isoformat()
            
            return self.store_preferences(session_id, existing_prefs)
            
        except Exception as e:
            logger.error(f"Error updating preferences: {e}")
            return False
    
    def delete_preferences(self, session_id: str) -> bool:
        """Delete user preferences"""
        try:
            if not self.redis_client:
                return False
            
            key = f"preferences:{session_id}"
            result = self.redis_client.delete(key)
            
            logger.info(f"Preferences deleted for session: {session_id}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Error deleting preferences: {e}")
            return False
    
    def extend_session(self, session_id: str) -> bool:
        """Extend session expiry"""
        try:
            if not self.redis_client:
                return False
            
            key = f"preferences:{session_id}"
            return self.redis_client.expire(key, self.session_expiry)
            
        except Exception as e:
            logger.error(f"Error extending session: {e}")
            return False
