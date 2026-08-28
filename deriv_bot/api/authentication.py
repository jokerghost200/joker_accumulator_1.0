import logging
import asyncio
from typing import Dict, Any, Optional
from api.websocket import DerivWebSocket
from api.deriv_rest import DerivREST

logger = logging.getLogger(__name__)

class DerivAuthenticator:
    def __init__(self, ws: DerivWebSocket, rest_api: DerivREST, account_type: str = "demo"):
        self.ws = ws
        self.rest_api = rest_api
        self.account_type = account_type.lower()
        self.is_authenticated = False
        self.account_info: Optional[Dict[str, Any]] = None

    async def authenticate(self) -> bool:
        """
        Executes the PAT -> REST -> OTP -> WebSocket authentication flow.
        """
        # 1. Fetch accounts via REST
        # Running synchronous requests in a thread to not block the asyncio loop
        accounts = await asyncio.to_thread(self.rest_api.get_accounts)
        
        if not accounts:
            logger.error("Could not retrieve accounts from REST API.")
            return False
            
        # 2. Find the target account ID based on account_type (demo vs real)
        target_account_id = None
        
        for acc in accounts:
            account_id = acc.get('account_id', '')
            is_demo = acc.get('account_type') == 'demo' or account_id.startswith('DOT') or account_id.startswith('VRT')
            
            if self.account_type == "demo" and is_demo:
                target_account_id = account_id
                self.account_info = acc
                break
            elif self.account_type != "demo" and not is_demo:
                target_account_id = account_id
                self.account_info = acc
                break
                
        if not target_account_id:
            # Fallback if we didn't match the exact pattern
            logger.warning(f"Could not find an account matching type '{self.account_type}'. Using the first available.")
            if accounts:
                target_account_id = accounts[0].get('account_id', '')
                self.account_info = accounts[0]
            else:
                return False
                
        logger.info(f"Target account selected: {target_account_id}")

        # 3. Get the Authenticated WS URL for the selected account
        auth_url = await asyncio.to_thread(self.rest_api.get_authenticated_url, target_account_id)
        if not auth_url:
            logger.error("Failed to retrieve authenticated WS URL.")
            return False
            
        logger.info("Authenticated WS URL successfully retrieved.")
        
        self.ws.endpoint = auth_url
        
        # 4. The websocket will use this URL on connect()
        self.is_authenticated = True
        logger.info("WebSocket URL updated with OTP for secure connection.")
        
        return True
