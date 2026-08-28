import asyncio
import logging
from typing import Dict, Any, Callable, List, Optional
from api.websocket import DerivWebSocket

logger = logging.getLogger(__name__)

class MarketDataSubscription:
    def __init__(self, ws: DerivWebSocket):
        self.ws = ws
        self.subscribed_symbols = set()
        self.tick_handlers: List[Callable[[Dict[str, Any]], Any]] = []
        self.history_handlers: List[Callable[[Dict[str, Any]], Any]] = []
        
        # Register main handler
        self.ws.add_handler(self._handle_message)

    async def subscribe_ticks(self, symbol: str) -> bool:
        """Subscribe to real-time tick stream for a symbol."""
        logger.info(f"Subscribing to ticks for {symbol}...")
        try:
            await self.ws.send({
                "ticks": symbol,
                "subscribe": 1
            })
            self.subscribed_symbols.add(symbol)
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to ticks for {symbol}: {e}")
            return False

    async def subscribe_ticks_history(self, symbol: str, count: int = 5000) -> bool:
        """Subscribe to real-time ticks stream and fetch history for a symbol."""
        logger.info(f"Subscribing to ticks history for {symbol} with {count} count...")
        try:
            await self.ws.send({
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "start": 1,
                "style": "ticks",
                "subscribe": 1
            })
            self.subscribed_symbols.add(f"{symbol}_ticks")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe to ticks history for {symbol}: {e}")
            return False

    async def get_historical_ticks(self, symbol: str, count: int = 5000) -> bool:
        """Fetch historical ticks data without subscribing."""
        logger.info(f"Fetching {count} historical ticks for {symbol}...")
        try:
            await self.ws.send({
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "style": "ticks"
            })
            return True
        except Exception as e:
            logger.error(f"Failed to fetch historical ticks for {symbol}: {e}")
            return False

    def add_tick_handler(self, handler: Callable[[Dict[str, Any]], Any]):
        if handler not in self.tick_handlers:
            self.tick_handlers.append(handler)

    def add_history_handler(self, handler: Callable[[Dict[str, Any]], Any]):
        if handler not in self.history_handlers:
            self.history_handlers.append(handler)

    def _handle_message(self, message: Dict[str, Any]):
        """Internal handler to route messages based on type."""
        msg_type = message.get("msg_type")
        
        if msg_type == "tick":
            for handler in self.tick_handlers:
                handler(message["tick"])
        elif msg_type == "history":
            for handler in self.history_handlers:
                handler(message["history"])
