import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class MarketDataCache:
    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self.df = pd.DataFrame(columns=['time', 'close'])
        self.df.set_index('time', inplace=True)

    def initialize_with_history(self, history: Dict[str, list]):
        """Initialize the cache with historical ticks from API."""
        if not history or 'prices' not in history or 'times' not in history:
            return
            
        # Deriv history format: {'prices': [...], 'times': [...]}
        try:
            times = pd.to_datetime(history['times'], unit='s')
            prices = [float(p) for p in history['prices']]
            
            new_df = pd.DataFrame({'time': times, 'close': prices})
            new_df.set_index('time', inplace=True)
            
            # Sort just in case
            new_df.sort_index(inplace=True)
            
            self.df = new_df
            self._trim_cache()
            
            logger.info(f"Initialized cache with {len(self.df)} ticks.")
        except Exception as e:
            logger.error(f"Error initializing cache with history: {e}")

    def update_tick(self, tick: Dict[str, Any]):
        """Update the cache with a new live tick."""
        try:
            timestamp = pd.to_datetime(tick['epoch'], unit='s')
            
            self.df.loc[timestamp] = [
                float(tick['quote'])
            ]
            
            # Remove old data if exceeding max_size
            self._trim_cache()
            
        except Exception as e:
            logger.error(f"Error updating candle: {e}")

    def get_dataframe(self) -> pd.DataFrame:
        """Get the current dataframe."""
        return self.df.copy()

    def _trim_cache(self):
        if len(self.df) > self.max_size:
            self.df = self.df.iloc[-self.max_size:]
