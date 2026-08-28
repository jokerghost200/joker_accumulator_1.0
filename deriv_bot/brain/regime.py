from enum import Enum
from dataclasses import dataclass

class TrendRegime(Enum):
    STRONG_UP = "STRONG_UP"
    WEAK_UP = "WEAK_UP"
    RANGING = "RANGING"
    WEAK_DOWN = "WEAK_DOWN"
    STRONG_DOWN = "STRONG_DOWN"

class VolatilityRegime(Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

@dataclass
class MarketState:
    trend: TrendRegime
    volatility: VolatilityRegime
    is_breaking_out: bool
    momentum_score: float  # -100 to 100
    structure_bullish: bool
    
    def __str__(self):
        return f"Trend: {self.trend.value}, Vol: {self.volatility.value}, Breakout: {self.is_breaking_out}, Mom: {self.momentum_score:.1f}, BullStruct: {self.structure_bullish}"
