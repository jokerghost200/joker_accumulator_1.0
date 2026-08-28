import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.websocket import DerivWebSocket
from api.authentication import DerivAuthenticator
from api.deriv_rest import DerivREST

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    load_dotenv()
    app_id = os.getenv("DERIV_APP_ID", "1089")
    api_token = os.getenv("DERIV_PAT")
    
    ws = DerivWebSocket(app_id=app_id)
    rest_api = DerivREST(app_id=app_id, pat=api_token)
    auth = DerivAuthenticator(ws, rest_api, account_type="demo")
    
    await auth.authenticate()
    await ws.connect()
    
    # Request Accumulator proposal for different growth rates
    for gr in [0.01, 0.02, 0.03, 0.04, 0.05]:
        request = {
            "proposal": 1,
            "amount": 10,
            "basis": "stake",
            "contract_type": "ACCU",
            "currency": "USD",
            "underlying_symbol": "R_10",
            "growth_rate": gr
        }
        
        resp = await ws.send_request(request)
        proposal = resp.get("proposal", {})
        high_barrier = proposal.get("high_barrier")
        low_barrier = proposal.get("low_barrier")
        spot = proposal.get("spot")
        
        if high_barrier and low_barrier and spot:
            hb = float(high_barrier)
            lb = float(low_barrier)
            sp = float(spot)
            
            upper_diff = (hb - sp) / sp
            lower_diff = (sp - lb) / sp
            
            logger.info(f"Growth {gr*100}% -> Spot: {sp}, High: {hb}, Low: {lb}")
            logger.info(f"Barrier % = Upper: +{upper_diff*100:.4f}%, Lower: -{lower_diff*100:.4f}%")
        else:
            logger.error(f"Error or missing fields for growth {gr}: {resp}")
            
    await ws.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
