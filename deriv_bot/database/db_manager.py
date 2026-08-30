import sqlite3
import os
import logging
from threading import Lock

logger = logging.getLogger("database.manager")

class StrategyDBManager:
    def __init__(self, db_path="database/strategies.db"):
        self.db_path = db_path
        self.lock = Lock()
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_hash TEXT PRIMARY KEY,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    win_rate REAL DEFAULT 0.0,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()

    def record_outcome(self, pattern_hash: str, is_win: bool):
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check if exists
                cursor.execute("SELECT wins, losses FROM patterns WHERE pattern_hash = ?", (pattern_hash,))
                row = cursor.fetchone()
                
                if row:
                    wins, losses = row
                    if is_win:
                        wins += 1
                    else:
                        losses += 1
                else:
                    wins = 1 if is_win else 0
                    losses = 0 if is_win else 1
                
                total = wins + losses
                win_rate = (wins / total) if total > 0 else 0.0
                
                cursor.execute('''
                    INSERT OR REPLACE INTO patterns (pattern_hash, wins, losses, win_rate, last_seen)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (pattern_hash, wins, losses, win_rate))
                
                conn.commit()
            except Exception as e:
                logger.error(f"Erreur SQL lors de l'enregistrement de l'outcome: {e}")
            finally:
                conn.close()

    def get_pattern_stats(self, pattern_hash: str):
        """Returns (wins, losses, win_rate) for a pattern hash, or None if not found."""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT wins, losses, win_rate FROM patterns WHERE pattern_hash = ?", (pattern_hash,))
                row = cursor.fetchone()
                conn.close()
                return row
            except Exception as e:
                logger.error(f"Erreur SQL lors de la lecture du pattern: {e}")
                return None
