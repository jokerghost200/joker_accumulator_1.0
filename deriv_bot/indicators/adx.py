import pandas as pd
import numpy as np

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index (ADX)."""
    up_move = high.diff()
    down_move = low.diff()
    
    # Calculate +DM and -DM
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm_series = pd.Series(plus_dm, index=high.index)
    minus_dm_series = pd.Series(minus_dm, index=high.index)
    
    # Calculate True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's Smoothing
    smoothed_tr = tr.ewm(alpha=1/period, adjust=False).mean()
    smoothed_plus_dm = plus_dm_series.ewm(alpha=1/period, adjust=False).mean()
    smoothed_minus_dm = minus_dm_series.ewm(alpha=1/period, adjust=False).mean()
    
    # Calculate +DI and -DI
    plus_di = 100 * (smoothed_plus_dm / smoothed_tr)
    minus_di = 100 * (smoothed_minus_dm / smoothed_tr)
    
    # Calculate DX
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    dx = dx.fillna(0)
    
    # Calculate ADX
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return adx
