import pandas as pd
import numpy as np

from indicators.ema import calculate_ema
from indicators.rsi import calculate_rsi
from indicators.macd import calculate_macd
from indicators.bollinger import calculate_bollinger_bands
from indicators.adx import calculate_adx
from indicators.atr import calculate_atr

class FeatureEngine:
    """Calculates all necessary technical features from a raw Tick DataFrame."""
    
    @staticmethod
    def enrich_data(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or len(df) < 50:
            return df
            
        data = df.copy()
        
        # 1. EMAs
        data['ema_9'] = calculate_ema(data['close'], 9)
        data['ema_20'] = calculate_ema(data['close'], 20)
        data['ema_50'] = calculate_ema(data['close'], 50)
        
        # 2. Tick RSI
        data['tick_rsi_14'] = calculate_rsi(data['close'], 14)
        
        # 3. MACD
        macd_line, signal_line, macd_hist = calculate_macd(data['close'])
        data['macd'] = macd_line
        data['macd_signal'] = signal_line
        data['macd_hist'] = macd_hist
        
        # 4. Bollinger Bands (Tick-based)
        lower_bb, mid_bb, upper_bb = calculate_bollinger_bands(data['close'], 20, 2.0)
        data['bb_lower'] = lower_bb
        data['bb_mid'] = mid_bb
        data['bb_upper'] = upper_bb
        data['bb_width'] = (upper_bb - lower_bb) / mid_bb
        
        # 5. Distances to Bollinger Bands (%)
        # This helps the model understand where the price is relative to the bands
        data['dist_bb_mid'] = (data['close'] - data['bb_mid']) / data['bb_mid'] * 100
        data['dist_bb_upper'] = (data['bb_upper'] - data['close']) / data['close'] * 100
        data['dist_bb_lower'] = (data['close'] - data['bb_lower']) / data['close'] * 100
        
        # 6. Tick Volatility (Standard Deviation of returns)
        # Using 14 ticks rolling standard deviation of percentage change
        returns = data['close'].pct_change()
        data['tick_volatility_14'] = returns.rolling(window=14).std() * 100
        
        # Volatility Variation (momentum of volatility)
        data['volatility_variation'] = data['tick_volatility_14'] - data['tick_volatility_14'].shift(5)
        
        # 7. Tick Momentum (Rate of Change)
        data['roc_5'] = data['close'].pct_change(periods=5) * 100
        data['roc_10'] = data['close'].pct_change(periods=10) * 100
        data['price_change_1'] = data['close'].diff(1)
        
        # 8. Accumulator Specific Features
        # Instantaneous absolute percentage change
        abs_pct = returns.abs()
        data['instant_volatility'] = abs_pct
        
        # Frequency of UP/DOWN movements
        is_up = (data['close'].diff(1) > 0).astype(int)
        data['up_freq_10'] = is_up.rolling(10).sum() / 10
        data['up_freq_20'] = is_up.rolling(20).sum() / 20
        
        # Average movement size
        data['avg_move_10'] = abs_pct.rolling(10).mean()
        data['avg_move_20'] = abs_pct.rolling(20).mean()
        
        # 9. New ML Enhancements (Pseudo-Candles)
        # Create 5-tick rolling high/low for ADX and ATR
        pseudo_high = data['close'].rolling(5).max()
        pseudo_low = data['close'].rolling(5).min()
        
        # Micro-Volatility (5-tick std dev)
        data['micro_volatility_5'] = returns.rolling(window=5).std() * 100
        
        # ADX (14 pseudo-candles)
        data['adx_14'] = calculate_adx(pseudo_high, pseudo_low, data['close'], period=14)
        
        # Mean Reversion Ratio: (Distance to EMA20) / Tick Volatility
        # Safe division
        safe_vol = data['tick_volatility_14'].replace(0, 0.0001)
        data['mean_reversion_ratio'] = ((data['close'] - data['ema_20']) / data['ema_20'] * 100) / safe_vol
        
        return data
