import pandas as pd
from typing import List, Dict, Any
import logging
from brain.feature_engine import FeatureEngine
from brain.market_state import MarketAnalyzer
from brain.signal_engine import SignalEngine
from brain.decision_engine import DecisionEngine
from strategies.base import SignalDirection

logger = logging.getLogger(__name__)

class BacktestResult:
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.trades = []
        self.wins = 0
        self.losses = 0
        self.max_capital = initial_capital
        self.min_capital = initial_capital
        
    def add_trade(self, trade: Dict[str, Any]):
        self.trades.append(trade)
        self.capital += trade['profit']
        
        if trade['profit'] > 0:
            self.wins += 1
        else:
            self.losses += 1
            
        self.max_capital = max(self.max_capital, self.capital)
        self.min_capital = min(self.min_capital, self.capital)
        
    def summary(self) -> Dict[str, Any]:
        total_trades = len(self.trades)
        win_rate = (self.wins / total_trades * 100) if total_trades > 0 else 0
        drawdown = ((self.max_capital - self.min_capital) / self.max_capital * 100) if self.max_capital > 0 else 0
        
        return {
            "Total Trades": total_trades,
            "Wins": self.wins,
            "Losses": self.losses,
            "Win Rate (%)": round(win_rate, 2),
            "Initial Capital": self.initial_capital,
            "Final Capital": round(self.capital, 2),
            "Net Profit": round(self.capital - self.initial_capital, 2),
            "Max Drawdown (%)": round(drawdown, 2)
        }

class Backtester:
    def __init__(
        self,
        feature_engine: FeatureEngine,
        signal_engine: SignalEngine,
        decision_engine: DecisionEngine,
        initial_capital: float = 1000.0,
        stake: float = 10.0,
        payout_rate: float = 0.85,  # 85% payout
        duration_candles: int = 3   # Trade duration in candles
    ):
        self.feature_engine = feature_engine
        self.signal_engine = signal_engine
        self.decision_engine = decision_engine
        self.initial_capital = initial_capital
        self.stake = stake
        self.payout_rate = payout_rate
        self.duration_candles = duration_candles
        
    def run(self, historical_data: pd.DataFrame) -> BacktestResult:
        """
        Runs a simulation on historical OHLC data.
        """
        logger.info(f"Starting backtest on {len(historical_data)} candles...")
        
        # 1. Calculate all features at once for speed
        enriched_data = self.feature_engine.calculate_features(historical_data)
        
        result = BacktestResult(self.initial_capital)
        
        # We need a minimum window to calculate the Market State and indicators properly
        # E.g. EMA200 needs at least 200 candles
        start_idx = 200 
        
        # To handle open trades (simple array holding (entry_price, direction, exit_index))
        active_trade = None
        
        for i in range(start_idx, len(enriched_data)):
            # Check if active trade is finished
            if active_trade is not None and i >= active_trade['exit_index']:
                # Resolve trade
                exit_candle = enriched_data.iloc[i]
                exit_price = exit_candle['close'] # Simplification: closing price of the exit candle
                
                direction = active_trade['direction']
                entry_price = active_trade['entry_price']
                
                won = False
                if direction == SignalDirection.HIGHER and exit_price > entry_price:
                    won = True
                elif direction == SignalDirection.LOWER and exit_price < entry_price:
                    won = True
                    
                profit = (self.stake * self.payout_rate) if won else -self.stake
                
                trade_record = {
                    "entry_time": active_trade['entry_time'],
                    "exit_time": exit_candle.name if hasattr(exit_candle, 'name') else i,
                    "direction": "HIGHER" if direction == SignalDirection.HIGHER else "LOWER",
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "profit": profit
                }
                
                result.add_trade(trade_record)
                active_trade = None
                
            # If no active trade, look for new signal
            if active_trade is None:
                # Slice data up to current index (simulate realtime)
                current_window = enriched_data.iloc[:i+1]
                
                # Market State
                state = MarketAnalyzer.analyze(current_window)
                if state is None:
                    continue
                    
                # Signal
                score, direction = self.signal_engine.generate_signal(current_window, state)
                
                # Decision
                # For backtesting, we skip ML probability check unless integrated
                decision = self.decision_engine.decide(
                    score=score, 
                    direction=direction, 
                    state=state, 
                    ml_probability=None, # To be added when ML is ready
                    payout=self.payout_rate
                )
                
                if decision != SignalDirection.WAIT:
                    # Enter trade
                    entry_candle = enriched_data.iloc[i]
                    active_trade = {
                        "entry_index": i,
                        "exit_index": i + self.duration_candles,
                        "direction": decision,
                        "entry_price": entry_candle['close'],
                        "entry_time": entry_candle.name if hasattr(entry_candle, 'name') else i
                    }
                    
        return result
