import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

class DerivWebSocket:
    def __init__(self, app_id: str, endpoint: str = "wss://ws.binaryws.com/websockets/v3"):
        self.app_id = app_id
        self.endpoint = f"{endpoint}?app_id={self.app_id}"
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.message_handlers = []
        self._loop = None
        self._keepalive_task = None
        self._req_id = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}

    async def connect(self):
        """Connect to Deriv WebSocket API."""
        try:
            logger.info(f"Connecting to {self.endpoint}...")
            # Disable protocol-level pings as Deriv might not respond to them properly
            self.ws = await websockets.connect(self.endpoint, ping_interval=None)
            self.connected = True
            logger.info("Connected successfully to Deriv WebSocket API.")
            
            # Start a listener task and a keepalive task
            self._loop = asyncio.create_task(self._listen_for_messages())
            self._keepalive_task = asyncio.create_task(self._keep_alive())
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            raise e

    async def disconnect(self):
        """Disconnect from Deriv WebSocket API."""
        if self.ws and self.connected:
            self.connected = False
            await self.ws.close()
            logger.info("Disconnected from Deriv WebSocket API.")
        if self._loop:
            self._loop.cancel()
        if self._keepalive_task:
            self._keepalive_task.cancel()

    async def _keep_alive(self):
        """Send an application-level ping every 30 seconds to keep the connection alive."""
        while self.connected:
            try:
                await asyncio.sleep(30)
                if self.connected:
                    await self.send({"ping": 1})
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Keepalive error: {e}")
                break

    async def send(self, message: Dict[str, Any]):
        """Send a JSON message to the WebSocket."""
        if not self.connected or not self.ws:
            logger.error("Cannot send message: WebSocket is not connected.")
            return

        try:
            msg_str = json.dumps(message)
            logger.debug(f"Sending: {msg_str}")
            await self.ws.send(msg_str)
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.connected = False
    async def send_request(self, message: Dict[str, Any], timeout: int = 10) -> Dict[str, Any]:
        """Send a message and wait for the correlated response."""
        self._req_id += 1
        req_id = self._req_id
        message["req_id"] = req_id
        
        future = asyncio.get_running_loop().create_future()
        self.pending_requests[req_id] = future
        
        await self.send(message)
        
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self.pending_requests.pop(req_id, None)
            logger.error(f"Request {req_id} timed out.")
            return {"error": {"message": "Request timeout"}}
    async def _listen_for_messages(self):
        """Listen for incoming messages and dispatch them to handlers."""
        if not self.ws:
            return
            
        try:
            async for message in self.ws:
                data = json.loads(message)
                logger.debug(f"Received: {data}")
                
                # Check for errors in the response
                if "error" in data:
                    logger.error(f"API Error: {data['error']}")
                
                # Resolve pending request if req_id is present
                if "req_id" in data:
                    req_id = data["req_id"]
                    if req_id in self.pending_requests:
                        future = self.pending_requests.pop(req_id)
                        if not future.done():
                            future.set_result(data)
                            
                # Dispatch to all registered handlers
                for handler in self.message_handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(data)
                        else:
                            handler(data)
                    except Exception as e:
                        logger.error(f"Error in message handler {handler.__name__}: {e}")
                        
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}")
            self.connected = False
        except asyncio.CancelledError:
            logger.info("Listener task cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error in listener: {e}")
            self.connected = False

    def add_handler(self, handler: Callable[[Dict[str, Any]], Any]):
        """Register a callback for incoming messages."""
        if handler not in self.message_handlers:
            self.message_handlers.append(handler)

    def remove_handler(self, handler: Callable[[Dict[str, Any]], Any]):
        """Remove a registered callback."""
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
