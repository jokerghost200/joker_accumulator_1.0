import logging
from typing import Dict, Any, Callable
from api.market_data import MarketDataSubscription
from data.cache import MarketDataCache

logger = logging.getLogger(__name__)

class DataEngine:
    def __init__(self, market_data: MarketDataSubscription, max_cache_size: int = 5000):
        self.market_data = market_data
        self.cache = MarketDataCache(max_size=max_cache_size)
        
        # Callbacks for new valid data
        self.on_new_tick_callbacks = []
        
        # Bind handlers
        self.market_data.add_history_handler(self._handle_history)
        self.market_data.add_tick_handler(self._handle_tick)
        
    def add_tick_callback(self, callback: Callable):
        """Register a callback that gets triggered when the cache is updated with a new tick."""
        if callback not in self.on_new_tick_callbacks:
            self.on_new_tick_callbacks.append(callback)
            
    def _handle_history(self, history: Dict[str, Any]):
        """Process incoming historical ticks data."""
        prices = history.get('prices', [])
        logger.info(f"DataEngine: Received historical ticks (size: {len(prices)})")
        self.cache.initialize_with_history(history)
        
        logger.info("Historical data loaded into cache.")
        self._notify_callbacks()

    def _handle_tick(self, tick: Dict[str, Any]):
        """Process incoming live ticks."""
        if 'quote' not in tick or 'epoch' not in tick:
            logger.warning("Received invalid tick.")
            return
            
        self.cache.update_tick(tick)
        
        # Notify callbacks on every tick so the strategy can react instantly
        self._notify_callbacks()

    def _notify_callbacks(self):
        df = self.cache.get_dataframe()
        for cb in self.on_new_tick_callbacks:
            try:
                cb(df)
            except Exception as e:
                logger.error(f"Error in tick callback: {e}")
