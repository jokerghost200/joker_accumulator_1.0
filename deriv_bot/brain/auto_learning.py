import os
import pandas as pd
import logging
import uuid
from typing import Dict, List, Any
import threading
from database.db_manager import StrategyDBManager
from brain.pattern_recognizer import PatternRecognizer

logger = logging.getLogger(__name__)

class VirtualTrade:
    def __init__(self, features: dict, start_price: float, target_ticks: int, barrier_pct: float, rate: float):
        self.id = str(uuid.uuid4())
        self.features = features.copy()
        self.target_ticks = target_ticks
        self.barrier_pct = barrier_pct
        self.rate = rate
        self.entry_price = start_price
        self.current_price = start_price
        self.ticks_survived = 0

class AutoLearner:
    def __init__(self, csv_path: str = "data/live_training.csv"):
        self.csv_path = csv_path
        self.active_trades: List[VirtualTrade] = []
        self.collected_outcomes = 0
        self.lock = threading.Lock()
        self.db = StrategyDBManager()
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        
        # Initialize CSV if it doesn't exist
        if not os.path.exists(self.csv_path):
            # We'll create headers when the first trade finishes
            self._headers_written = False
        else:
            self._headers_written = True

    def start_tracking(self, features: dict, start_price: float, target_ticks: int, barrier_pct: float, rate: float):
        """Start simulating a trade for a specific growth rate."""
        # Add target_ticks and barrier_threshold to features exactly as the model expects them
        feat_to_save = features.copy()
        feat_to_save['target_ticks'] = target_ticks
        feat_to_save['barrier_threshold'] = barrier_pct
        
        trade = VirtualTrade(feat_to_save, start_price, target_ticks, barrier_pct, rate)
        with self.lock:
            self.active_trades.append(trade)
            
    def update_with_tick(self, new_price: float) -> int:
        """
        Evaluate active virtual trades with the new tick.
        Returns the number of newly collected outcomes.
        """
        finished_trades = []
        new_outcomes = 0
        
        with self.lock:
            for trade in self.active_trades:
                trade.ticks_survived += 1
                
                # Check barrier relative to PREVIOUS price (Accumulator logic)
                distance = abs(new_price - trade.current_price) / trade.current_price
                
                if distance >= trade.barrier_pct:
                    # KNOCKOUT
                    self._save_outcome(trade, outcome=0)
                    finished_trades.append(trade)
                    new_outcomes += 1
                elif trade.ticks_survived >= trade.target_ticks:
                    # SURVIVED
                    self._save_outcome(trade, outcome=1)
                    finished_trades.append(trade)
                    new_outcomes += 1
                else:
                    # STILL ALIVE, update current_price for next tick!
                    trade.current_price = new_price
            
            # Remove finished trades
            for t in finished_trades:
                self.active_trades.remove(t)
                
        self.collected_outcomes += new_outcomes
        return new_outcomes
        
    def _save_outcome(self, trade: VirtualTrade, outcome: int):
        data_row = trade.features.copy()
        data_row['survived'] = outcome
        
        df = pd.DataFrame([data_row])
        
        # Save to Golden Pattern DB
        try:
            pattern_hash = PatternRecognizer.get_pattern_hash(trade.features)
            is_win = (outcome == 1)
            self.db.record_outcome(pattern_hash, is_win)
        except Exception as e:
            logger.error(f"Failed to record golden pattern: {e}")

        # Determine if we should write headers
        write_header = not self._headers_written
        
        # Append to CSV
        try:
            df.to_csv(self.csv_path, mode='a', header=write_header, index=False)
            if write_header:
                self._headers_written = True
        except Exception as e:
            logger.error(f"Failed to save auto-learning data: {e}")
            
    def reset_counter(self):
        self.collected_outcomes = 0
