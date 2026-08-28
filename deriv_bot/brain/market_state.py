import pandas as pd
from brain.regime import MarketState, TrendRegime, VolatilityRegime

class MarketAnalyzer:
    """Analyzes enriched dataframe to determine the market regime."""
    
    @staticmethod
    def analyze(data: pd.DataFrame) -> MarketState:
        if data.empty or len(data) < 2:
            return None
            
        latest = data.iloc[-1]
        
        trend = MarketAnalyzer._determine_trend(latest)
        volatility = MarketAnalyzer._determine_volatility(latest)
        breakout = MarketAnalyzer._detect_breakout(data)
        momentum = MarketAnalyzer._calculate_momentum(latest)
        structure = MarketAnalyzer._analyze_structure(data)
        
        return MarketState(
            trend=trend,
            volatility=volatility,
            is_breaking_out=breakout,
            momentum_score=momentum,
            structure_bullish=structure
        )
        
    @staticmethod
    def _determine_trend(latest: pd.Series) -> TrendRegime:
        # Using EMAs and ADX
        close = latest['close']
        ema20, ema50, ema200 = latest.get('ema_20'), latest.get('ema_50'), latest.get('ema_200')
        adx = latest.get('adx_14', 0)
        
        if pd.isna(ema200):
            return TrendRegime.RANGING
            
        is_bullish_alignment = close > ema20 > ema50 > ema200
        is_bearish_alignment = close < ema20 < ema50 < ema200
        
        if adx > 25:
            if is_bullish_alignment:
                return TrendRegime.STRONG_UP if adx > 35 else TrendRegime.WEAK_UP
            elif is_bearish_alignment:
                return TrendRegime.STRONG_DOWN if adx > 35 else TrendRegime.WEAK_DOWN
                
        if close > ema50 and ema20 > ema50:
            return TrendRegime.WEAK_UP
        if close < ema50 and ema20 < ema50:
            return TrendRegime.WEAK_DOWN
            
        return TrendRegime.RANGING

    @staticmethod
    def _determine_volatility(latest: pd.Series) -> VolatilityRegime:
        bb_width = latest.get('bb_width', 0)
        
        if bb_width < 0.005:  # Arbitrary threshold, should be dynamic/percentile based on history
            return VolatilityRegime.LOW
        elif bb_width < 0.015:
            return VolatilityRegime.NORMAL
        elif bb_width < 0.03:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    @staticmethod
    def _detect_breakout(data: pd.DataFrame) -> bool:
        latest = data.iloc[-1]
        prev = data.iloc[-2]
        
        # Simple breakout: price closing outside BB after a low volatility period
        bb_upper, bb_lower = latest.get('bb_upper'), latest.get('bb_lower')
        
        if pd.isna(bb_upper):
            return False
            
        breaking_up = prev['close'] <= prev.get('bb_upper', 0) and latest['close'] > bb_upper
        breaking_down = prev['close'] >= prev.get('bb_lower', 0) and latest['close'] < bb_lower
        
        return breaking_up or breaking_down

    @staticmethod
    def _calculate_momentum(latest: pd.Series) -> float:
        # Scale RSI (0-100) and MACD to a -100 to +100 score
        rsi = latest.get('rsi_14', 50)
        macd_hist = latest.get('macd_hist', 0)
        
        rsi_score = (rsi - 50) * 2  # Maps 0-100 to -100 to +100
        macd_score = 50 if macd_hist > 0 else -50
        
        # Combine
        momentum = (rsi_score * 0.6) + (macd_score * 0.4)
        return max(min(momentum, 100), -100)
        
    @staticmethod
    def _analyze_structure(data: pd.DataFrame) -> bool:
        # True = Bullish structure (Higher highs, Higher lows)
        # Check last 20 candles for swing highs/lows
        recent = data.iloc[-20:]
        highs = recent[recent['swing_high'] == True]['high']
        lows = recent[recent['swing_low'] == True]['low']
        
        if len(highs) >= 2 and len(lows) >= 2:
            hh = highs.iloc[-1] > highs.iloc[-2]
            hl = lows.iloc[-1] > lows.iloc[-2]
            return hh and hl
            
        # Fallback to simple SMA relation
        return data['close'].iloc[-1] > data['close'].rolling(20).mean().iloc[-1]
