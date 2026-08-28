import logging
import requests
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class DerivREST:
    BASE_URL = "https://api.derivws.com/trading/v1"

    def __init__(self, app_id: str, pat: str):
        self.app_id = app_id
        self.pat = pat
        self.headers = {
            "Deriv-App-ID": str(self.app_id),
            "Authorization": f"Bearer {self.pat}",
            "Content-Type": "application/json"
        }
        
    def get_accounts(self) -> List[Dict[str, Any]]:
        """
        Fetches the list of all trading accounts.
        """
        url = f"{self.BASE_URL}/options/accounts"
        try:
            logger.info("Fetching accounts list from REST API...")
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info(f"REST API Response for accounts: {data}")
            if isinstance(data, dict):
                return data.get('data', data.get('accounts', []))
            elif isinstance(data, list):
                return data
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch accounts: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return []
            
    def get_authenticated_url(self, account_id: str) -> Optional[str]:
        """
        Requests an authenticated WebSocket URL for a given account.
        """
        url = f"{self.BASE_URL}/options/accounts/{account_id}/otp"
        try:
            logger.info(f"Requesting authenticated WS URL for account {account_id}...")
            response = requests.post(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            logger.info(f"REST API Response for OTP: {data}")
            
            # The URL is returned inside the 'data' object
            ws_url = data.get('data', {}).get('url')
            if not ws_url:
                logger.error("No URL found in the response.")
            return ws_url
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch authenticated URL: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None
