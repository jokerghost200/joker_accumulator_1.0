import asyncio, websockets, json
async def test():
    async with websockets.connect('wss://ws.binaryws.com/websockets/v3?app_id=1089') as ws:
        await ws.send(json.dumps({
            'proposal':1,
            'amount':5,
            'basis':'stake',
            'contract_type':'ACCU',
            'currency':'USD',
            'symbol':'R_10',
            'growth_rate':0.01
        }))
        res = await ws.recv()
        print(res)
asyncio.run(test())
