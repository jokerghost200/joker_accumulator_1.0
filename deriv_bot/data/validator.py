import logging
import pandas as pd
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class DataValidator:
    def __init__(self, expected_interval_seconds: int = 60):
        self.expected_interval = expected_interval_seconds
        
    def validate_historical_data(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """Validate a dataframe of historical candles."""
        if df.empty:
            return False, "Dataframe is empty."
            
        if len(df) < 50:
            return False, f"Not enough data points. Expected >= 50, got {len(df)}."
            
        # Check for NaN values
        if df.isnull().values.any():
            return False, "Data contains NaN values."
            
        # Check for 0 or negative prices
        if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
            return False, "Data contains 0 or negative prices."
            
        # Check continuity (optional strict check, could be a warning instead of hard fail)
        time_diffs = df.index.to_series().diff().dt.total_seconds().dropna()
        max_diff = time_diffs.max()
        
        # If there's a gap more than 2x the interval, we might be missing data
        # Note: on weekends some markets are closed, so this depends on the market.
        # For synthetic indices (Volatility 10 etc), they run 24/7 so gaps are actual missing data.
        if max_diff > (self.expected_interval * 2):
            logger.warning(f"Data gap detected. Max diff: {max_diff}s (expected ~{self.expected_interval}s)")
            # We don't fail validation just for a gap, but we log it.
            
        return True, "Data is valid."
        
    def validate_tick(self, tick: Dict[str, Any]) -> bool:
        """Validate a single incoming tick."""
        if 'quote' not in tick or 'epoch' not in tick:
            return False
            
        try:
            quote = float(tick['quote'])
            if quote <= 0:
                return False
        except (ValueError, TypeError):
            return False
            
        return True
