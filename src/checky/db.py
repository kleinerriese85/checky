"""
Database layer for Checky configuration management.

This module provides SQLite database operations for storing and managing
user configuration including child age, PIN authentication, and TTS voice preferences.
"""

import sqlite3
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    import hashlib
    # Fallback for bcrypt functionality (less secure, for development only)
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CheckyDatabase:
    """
    SQLite database manager for Checky user configuration.
    
    Handles secure storage of child age, PIN (hashed with bcrypt), 
    and TTS voice preferences.
    """
    
    def __init__(self, db_path: str = "checky.db"):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._ensure_database()
    
    def _ensure_database(self):
        """Create database and tables if they don't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_config (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        child_age INTEGER NOT NULL CHECK (child_age >= 5 AND child_age <= 10),
                        pin_hash TEXT NOT NULL,
                        tts_voice TEXT NOT NULL DEFAULT 'de-DE-Standard-A',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create trigger to automatically update updated_at
                conn.execute("""
                    CREATE TRIGGER IF NOT EXISTS update_user_config_timestamp
                    AFTER UPDATE ON user_config
                    FOR EACH ROW
                    BEGIN
                        UPDATE user_config SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                    END
                """)
                
                conn.commit()
                logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    def create_user(self, age: int, pin: str, tts_voice: str = "de-DE-Standard-A") -> bool:
        """
        Create a new user configuration.
        
        Args:
            age: Child's age (5-10)
            pin: 4-digit PIN for parent authentication
            tts_voice: Voice ID for text-to-speech
            
        Returns:
            True if user was created successfully, False otherwise
        """
        if not self._validate_age(age):
            logger.error(f"Invalid age: {age}. Must be between 5 and 10.")
            return False
        
        if not self._validate_pin(pin):
            logger.error("Invalid PIN format. Must be 4 digits.")
            return False
        
        try:
            # Hash the PIN for secure storage
            if BCRYPT_AVAILABLE:
                pin_hash = bcrypt.hashpw(pin.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            else:
                # Fallback hash (development only - not secure for production)
                pin_hash = hashlib.sha256(pin.encode('utf-8')).hexdigest()
            
            with sqlite3.connect(self.db_path) as conn:
                # Check if a user already exists
                cursor = conn.execute("SELECT COUNT(*) FROM user_config")
                if cursor.fetchone()[0] > 0:
                    logger.warning("User configuration already exists. Use update_config instead.")
                    return False
                
                # Insert new user configuration
                conn.execute(
                    "INSERT INTO user_config (child_age, pin_hash, tts_voice) VALUES (?, ?, ?)",
                    (age, pin_hash, tts_voice)
                )
                conn.commit()
                logger.info(f"User created successfully with age {age}")
                return True
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            return False
    
    def authenticate_pin(self, pin: str) -> bool:
        """
        Authenticate a PIN against the stored hash.
        
        Args:
            pin: 4-digit PIN to authenticate
            
        Returns:
            True if PIN is correct, False otherwise
        """
        if not self._validate_pin(pin):
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT pin_hash FROM user_config LIMIT 1")
                row = cursor.fetchone()
                
                if not row:
                    logger.warning("No user configuration found")
                    return False
                
                stored_hash = row[0]
                if BCRYPT_AVAILABLE:
                    return bcrypt.checkpw(pin.encode('utf-8'), stored_hash.encode('utf-8'))
                else:
                    # Fallback comparison (development only - not secure for production)
                    pin_hash = hashlib.sha256(pin.encode('utf-8')).hexdigest()
                    return pin_hash == stored_hash
        except Exception as e:
            logger.error(f"Failed to authenticate PIN: {e}")
            return False
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """
        Get the current user configuration.
        
        Returns:
            Dictionary with configuration data or None if no config exists
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT id, child_age, tts_voice, created_at, updated_at FROM user_config LIMIT 1"
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row["id"],
                    "child_age": row["child_age"],
                    "tts_voice": row["tts_voice"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                }
        except Exception as e:
            logger.error(f"Failed to get configuration: {e}")
            return None
    
    def update_config(self, age: Optional[int] = None, tts_voice: Optional[str] = None) -> bool:
        """
        Update user configuration.
        
        Args:
            age: New child's age (5-10), if provided
            tts_voice: New TTS voice ID, if provided
            
        Returns:
            True if update was successful, False otherwise
        """
        if age is not None and not self._validate_age(age):
            logger.error(f"Invalid age: {age}. Must be between 5 and 10.")
            return False
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if user exists
                cursor = conn.execute("SELECT id FROM user_config LIMIT 1")
                if not cursor.fetchone():
                    logger.error("No user configuration found to update")
                    return False
                
                # Build update query dynamically based on provided parameters
                updates = []
                params = []
                
                if age is not None:
                    updates.append("child_age = ?")
                    params.append(age)
                
                if tts_voice is not None:
                    updates.append("tts_voice = ?")
                    params.append(tts_voice)
                
                if not updates:
                    logger.warning("No parameters provided for update")
                    return False
                
                query = f"UPDATE user_config SET {', '.join(updates)} WHERE id = (SELECT id FROM user_config LIMIT 1)"
                conn.execute(query, params)
                conn.commit()
                
                logger.info(f"Configuration updated successfully")
                return True
        except Exception as e:
            logger.error(f"Failed to update configuration: {e}")
            return False
    
    def delete_user(self) -> bool:
        """
        Delete user configuration (for testing/reset purposes).
        
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM user_config")
                conn.commit()
                logger.info("User configuration deleted")
                return True
        except Exception as e:
            logger.error(f"Failed to delete user configuration: {e}")
            return False
    
    def _validate_age(self, age: int) -> bool:
        """Validate that age is between 5 and 10."""
        return isinstance(age, int) and 5 <= age <= 10
    
    def _validate_pin(self, pin: str) -> bool:
        """Validate that PIN is exactly 4 digits."""
        return isinstance(pin, str) and pin.isdigit() and len(pin) == 4


# Singleton instance for global use
_db_instance: Optional[CheckyDatabase] = None

def get_database(db_path: str = "checky.db") -> CheckyDatabase:
    """
    Get the global database instance.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        CheckyDatabase instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = CheckyDatabase(db_path)
    return _db_instance


# Convenience functions for easier usage
def create_user(age: int, pin: str, tts_voice: str = "de-DE-Standard-A") -> bool:
    """Create a new user configuration."""
    return get_database().create_user(age, pin, tts_voice)


def authenticate_pin(pin: str) -> bool:
    """Authenticate a PIN."""
    return get_database().authenticate_pin(pin)


def get_config() -> Optional[Dict[str, Any]]:
    """Get the current user configuration."""
    return get_database().get_config()


def update_config(age: Optional[int] = None, tts_voice: Optional[str] = None) -> bool:
    """Update user configuration."""
    return get_database().update_config(age, tts_voice)