import asyncio
import pandas as pd
import logging
import os
import math
from typing import Dict, Any

from api.websocket import DerivWebSocket
from brain.feature_engine import FeatureEngine
from brain.ml_filter import MLFilter

logger = logging.getLogger(__name__)

class Backtester:
    def __init__(self, app_id="1089"):
        self.app_id = app_id
        self.ws = DerivWebSocket(app_id=self.app_id)
        self.feature_engine = FeatureEngine()
        model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "rf_model.joblib")
        self.ml_filter = MLFilter(model_path=model_path)
        
        self.growth_rates = [0.01, 0.02, 0.03, 0.04, 0.05]
        
    async def fetch_history(self, symbol="R_10", count=3000) -> pd.DataFrame:
        logger.info(f"Connecting to public WS to fetch {count} ticks for backtest...")
        await self.ws.connect()
        
        request = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "style": "ticks"
        }
        
        response = await self.ws.send_request(request, timeout=30)
        await self.ws.disconnect()
        
        if 'error' in response:
            raise Exception(f"Failed to fetch historical data: {response['error'].get('message')}")
            
        history = response.get('history', {})
        prices = history.get('prices', [])
        times = history.get('times', [])
        
        if not prices or not times:
            raise Exception("No ticks received.")
            
        df = pd.DataFrame({
            'time': pd.to_datetime(times, unit='s'),
            'close': [float(p) for p in prices]
        })
        return df

    def run_backtest(self, df: pd.DataFrame, initial_balance=100.0, stake=5.0) -> Dict[str, Any]:
        """
        Runs a simplified tick-by-tick backtest on historical data.
        """
        logger.info("Enriching backtest data...")
        enriched = self.feature_engine.enrich_data(df)
        if enriched.empty or len(enriched) < 50:
            return {"error": "Not enough data"}
            
        balance = initial_balance
        trades_taken = 0
        wins = 0
        losses = 0
        
        active_trade = None
        
        # We start from index 50 to have enough history for features
        for i in range(50, len(enriched)):
            current_row = enriched.iloc[i]
            current_price = current_row['close']
            
            # If we are in a trade, check outcome
            if active_trade:
                # Check survival (Accumulators check distance from PREVIOUS tick, not entry price)
                change = abs((current_price - active_trade['current_price']) / active_trade['current_price'])
                if change >= active_trade['barrier']:
                    # Lost
                    losses += 1
                    active_trade = None
                else:
                    active_trade['current_price'] = current_price
                    active_trade['ticks_survived'] += 1
                    if active_trade['ticks_survived'] >= active_trade['target_ticks']:
                        # Won
                        wins += 1
                        balance += active_trade['profit']
                        active_trade = None
                continue
                
            # The user wants to trade purely based on the AI's tick probability
            # We bypass the manual technical conditions (Squeeze/RSI) and ask the AI on EVERY tick
            signal_detected = True
            
            if signal_detected:
                # Get best rate
                best_prob = 0
                best_rate = None
                best_ticks = 0
                best_barrier = 0
                
                # Mock extracting barriers since we don't have the API here
                # Realistic barriers for R_10 are around 0.006% (0.00006)
                for rate in self.growth_rates:
                    # 1% -> 0.000061, 5% -> 0.000048
                    approx_barrier = 0.000065 - (rate * 0.0003) 
                    target_ticks = math.ceil(math.log(1 + 0.25) / math.log(1 + rate))
                    
                    df_slice = enriched.iloc[:i+1]
                    prob = self.ml_filter.predict_survival(df_slice, target_ticks, approx_barrier)
                    
                    if prob > best_prob:
                        best_prob = prob
                        best_rate = rate
                        best_ticks = target_ticks
                        best_barrier = approx_barrier
                        
                if best_prob > 0.60:
                    trades_taken += 1
                    balance -= stake
                    profit = stake * 1.25 # TP = 25% for simplified backtest
                    
                    active_trade = {
                        'target_ticks': best_ticks,
                        'barrier': best_barrier,
                        'ticks_survived': 0,
                        'entry_price': current_price,
                        'current_price': current_price,
                        'profit': profit + stake # Return stake + profit
                    }
                    
        winrate = (wins / trades_taken * 100) if trades_taken > 0 else 0
        profit_total = balance - initial_balance
        
        return {
            "initial_balance": initial_balance,
            "final_balance": balance,
            "net_profit": profit_total,
            "trades": trades_taken,
            "wins": wins,
            "losses": losses,
            "winrate": winrate
        }
