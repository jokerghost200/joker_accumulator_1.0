import asyncio, os, json
import sys
sys.path.append("c:\\Users\\JOKER\\Desktop\\joker\\deriv_bot")
from api.websocket import DerivWebSocket
from api.authentication import DerivAuthenticator
from api.deriv_rest import DerivREST
from api.execution import ExecutionEngine
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.ERROR)

load_dotenv("c:\\Users\\JOKER\\Desktop\\joker\\deriv_bot\\.env")
app_id = os.getenv('DERIV_APP_ID', '1089')
api_token = os.getenv('DERIV_PAT')

async def main():
    ws = DerivWebSocket(app_id=app_id)
    rest_api = DerivREST(app_id=app_id, pat=api_token)
    auth = DerivAuthenticator(ws, rest_api, account_type='demo')
    await auth.authenticate()
    await ws.connect()
    
    execution = ExecutionEngine(ws)
    proposal = await execution.get_proposal('R_10', 'ACCU', 5.0, growth_rate=0.03)
    
    print(json.dumps(proposal, indent=2))
    
    await ws.disconnect()

asyncio.run(main())
