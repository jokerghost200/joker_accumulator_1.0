import asyncio
import os
import logging
from dotenv import load_dotenv

from api.websocket import DerivWebSocket
from api.authentication import DerivAuthenticator
from api.deriv_rest import DerivREST
from api.execution import ExecutionEngine
from utils.logger import setup_logger

async def close_all_positions():
    load_dotenv()
    logger = setup_logger()
    logger.info("Starting Open Positions Cleanup...")
    
    app_id = os.getenv("DERIV_APP_ID", "1089")
    api_token = os.getenv("DERIV_PAT")
    account_type = os.getenv("DERIV_ACCOUNT_TYPE", "demo")
    
    if not api_token:
        logger.error("DERIV_PAT not found in .env")
        return
        
    ws = DerivWebSocket(app_id=app_id)
    rest_api = DerivREST(app_id=app_id, pat=api_token)
    auth = DerivAuthenticator(ws, rest_api, account_type=account_type)
    execution = ExecutionEngine(ws)
    
    try:
        await ws.connect()
        authenticated = await auth.authenticate()
        if not authenticated:
            logger.error("Authentication failed. Cannot close positions.")
            return
            
        logger.info("Fetching portfolio...")
        response = await ws.send_request({"portfolio": 1})
        
        if 'error' in response:
            logger.error(f"Error fetching portfolio: {response['error'].get('message')}")
            return
            
        portfolio = response.get('portfolio', {})
        contracts = portfolio.get('contracts', [])
        
        if not contracts:
            logger.info("No open positions found. You are good to go!")
            return
            
        logger.info(f"Found {len(contracts)} open position(s). Closing all...")
        
        for contract in contracts:
            contract_id = contract.get('contract_id')
            symbol = contract.get('symbol')
            contract_type = contract.get('contract_type')
            logger.info(f"Selling {contract_type} on {symbol} (ID: {contract_id})")
            
            await execution.sell_contract(contract_id=contract_id, price=0)
            
        logger.info("Cleanup complete.")
        
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)
    finally:
        await ws.disconnect()

if __name__ == "__main__":
    asyncio.run(close_all_positions())
