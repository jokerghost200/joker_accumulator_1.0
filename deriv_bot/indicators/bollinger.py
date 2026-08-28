import pandas as pd
from typing import Tuple

def calculate_bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.
    Returns: (lower_band, middle_band, upper_band)
    """
    middle_band = series.rolling(window=period).mean()
    std_dev = series.rolling(window=period).std()
    
    upper_band = middle_band + (std_dev * num_std)
    lower_band = middle_band - (std_dev * num_std)
    
    return lower_band, middle_band, upper_band
