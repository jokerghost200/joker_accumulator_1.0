import logging
import asyncio
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self, websocket_client):
        self.ws = websocket_client
        
    async def buy_contract(self, proposal_id: str, price: float) -> Optional[Dict[str, Any]]:
        """
        Executes a buy order for a given proposal ID.
        """
        request = {
            "buy": proposal_id,
            "price": price
        }
        
        logger.info(f"Sending BUY request for proposal {proposal_id} at max price {price}")
        response = await self.ws.send_request(request)
        
        if 'error' in response:
            logger.error(f"Buy failed: {response['error'].get('message')}")
            return None
            
        buy_result = response.get('buy', {})
        logger.info(f"Buy successful! Contract ID: {buy_result.get('contract_id')}, Balance after: {buy_result.get('balance_after')}")
        
        return buy_result
        
    async def sell_contract(self, contract_id: int, price: float = 0) -> Optional[Dict[str, Any]]:
        """
        Executes a sell order for a given contract ID.
        By default, price=0 means sell at the current market price.
        """
        request = {
            "sell": contract_id,
            "price": price
        }
        
        logger.info(f"Sending SELL request for contract {contract_id} at price {price}")
        response = await self.ws.send_request(request)
        
        if 'error' in response:
            logger.error(f"Sell failed: {response['error'].get('message')}")
            return None
            
        sell_result = response.get('sell', {})
        logger.info(f"Sell successful! Contract ID: {sell_result.get('contract_id')}, Sold for: {sell_result.get('sold_for')}")
        
        return sell_result
        
    async def get_proposal(self, symbol: str, contract_type: str, stake: float, duration: int = 0, duration_unit: str = "t", **kwargs) -> Dict[str, Any]:
        """
        Requests a proposal for a contract to get the payout and proposal_id.
        contract_type: "CALL" (Higher), "PUT" (Lower), "ACCU" (Accumulator)
        duration_unit: "t" (ticks), "s" (seconds), "m" (minutes), "h" (hours), "d" (days)
        kwargs: can include 'growth_rate', 'limit_order', etc.
        """
        request = {
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": "USD",
            "underlying_symbol": symbol
        }
        
        if duration > 0:
            request["duration"] = duration
            request["duration_unit"] = duration_unit
            
        # Add any extra parameters (like growth_rate, limit_order)
        for key, value in kwargs.items():
            request[key] = value
        
        logger.info(f"Requesting proposal for {contract_type} on {symbol} (Stake: {stake})")
        response = await self.ws.send_request(request)
        
        return response

    async def subscribe_to_open_contract(self, contract_id: int, callback):
        """
        Subscribes to updates for an open contract.
        The callback will be invoked whenever an update is received.
        """
        request = {
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1
        }
        
        def handler(message):
            if 'proposal_open_contract' in message:
                poc = message.get('proposal_open_contract')
                if poc and str(poc.get('contract_id')) == str(contract_id):
                    callback(poc)
        
        self.ws.message_handlers.append(handler)
        
        logger.info(f"Subscribing to open contract: {contract_id}")
        await self.ws.send(request)
