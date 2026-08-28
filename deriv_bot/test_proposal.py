import asyncio
import websockets
import json

async def main():
    # Let's test against the normal Deriv endpoint
    async with websockets.connect("wss://ws.binaryws.com/websockets/v3?app_id=1089") as ws:
        request = {
            "proposal": 1,
            "amount": 10,
            "basis": "stake",
            "contract_type": "CALL",
            "currency": "USD",
            "duration": 1,
            "duration_unit": "m",
            "symbol": "R_100"
        }
        await ws.send(json.dumps(request))
        resp = await ws.recv()
        print(resp)

asyncio.run(main())
