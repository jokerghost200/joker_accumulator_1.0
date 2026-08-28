import pandas as pd
from typing import Tuple
from indicators.ema import calculate_ema

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).
    Returns: (macd_line, signal_line, macd_histogram)
    """
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    macd_histogram = macd_line - signal_line
    
    return macd_line, signal_line, macd_histogram
