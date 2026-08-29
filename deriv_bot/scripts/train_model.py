import os
import sys
import asyncio
import logging
import pandas as pd
from dotenv import load_dotenv

# Add parent directory to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.websocket import DerivWebSocket
from api.authentication import DerivAuthenticator
from api.market_data import MarketDataSubscription
from brain.feature_engine import FeatureEngine
from brain.ml_filter import MLFilter
from api.deriv_rest import DerivREST

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    
    # We force a public app_id (1089 is Deriv's general public ID) because the one in .env is invalid (not numeric)
    app_id = "1089"
    api_token = os.getenv("DERIV_PAT")
    
    ws = DerivWebSocket(app_id=app_id)
    
    # We do not need authentication to fetch historical ticks
    # This avoids REST API timeouts
    logger.info("Connecting to public WebSocket URL...")
    await ws.connect()
    
    # We want a lot of data to train the model, say 3000 candles (5000 sometimes times out on Deriv)
    symbol = "R_10"
    count = 3000
    
    logger.info(f"Fetching {count} historical ticks for {symbol}...")
    
    request = {
        "ticks_history": symbol,
        "adjust_start_time": 1,
        "count": count,
        "end": "latest",
        "style": "ticks"
    }
    
    response = await ws.send_request(request, timeout=30)
    
    if 'error' in response:
        logger.error(f"Failed to fetch historical data: {response['error'].get('message')}")
        await ws.disconnect()
        sys.exit(1)
        
    history = response.get('history', {})
    prices = history.get('prices', [])
    times = history.get('times', [])
    
    if not prices or not times:
        logger.error("No ticks received.")
        await ws.disconnect()
        sys.exit(1)
        
    df = pd.DataFrame({
        'time': pd.to_datetime(times, unit='s'),
        'close': [float(p) for p in prices]
    })
    
    logger.info(f"Received {len(df)} ticks. Enriching data...")
    
    feature_engine = FeatureEngine()
    enriched_df = feature_engine.enrich_data(df)
    
    logger.info("Initializing ML Filter for training...")
    # Ensure the model path is relative to the project root
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "rf_model.joblib")
    ml_filter = MLFilter(model_path=model_path)
    
    logger.info("Training ML model...")
    ml_filter.train(enriched_df)
    
    await ws.disconnect()
    logger.info("Training complete!")

if __name__ == "__main__":
    asyncio.run(main())
