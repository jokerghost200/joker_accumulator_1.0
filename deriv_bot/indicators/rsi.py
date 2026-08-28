import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    delta = series.diff()
    
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero
    rsi = rsi.replace([np.inf, -np.inf], 100)
    
    return rsi
