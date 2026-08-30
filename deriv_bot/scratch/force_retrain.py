import asyncio
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from brain.backtest_engine import Backtester

logging.basicConfig(level=logging.INFO, format='%(message)s')

async def main():
    print("Fetching 5000 ticks from Deriv API...")
    engine = Backtester()
    try:
        df = await engine.fetch_history(symbol="R_10", count=5000)
        print(f"Got {len(df)} ticks. Retraining AI model properly...")
        
        enriched = engine.feature_engine.enrich_data(df)
        engine.ml_filter.train(enriched)
        
        print("Model retraining successful!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
