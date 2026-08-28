import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

load_dotenv()
PAT = os.getenv("DERIV_PAT")
APP_ID = "1089"  # testing with standard app_id first

async def main():
    uri = f"wss://ws.binaryws.com/websockets/v3?app_id={APP_ID}"
    print(f"Connecting to {uri} with PAT: {PAT}")
    async with websockets.connect(uri) as ws:
        auth_req = {"authorize": PAT}
        await ws.send(json.dumps(auth_req))
        resp = await ws.recv()
        print("Auth response:", resp)
        if "error" not in json.loads(resp):
            print("Authorized successfully!")
            proposal = {
                "proposal": 1,
                "amount": 10,
                "basis": "stake",
                "contract_type": "CALL",
                "currency": "USD",
                "duration": 1,
                "duration_unit": "m",
                "symbol": "R_100"
            }
            await ws.send(json.dumps(proposal))
            prop_resp = await ws.recv()
            print("Proposal response:", prop_resp)

asyncio.run(main())
