import asyncio
import websockets
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()
PAT = os.getenv("DERIV_PAT")
APP_ID = os.getenv("DERIV_APP_ID")

def get_auth_url():
    url = "https://api.derivws.com/trading/v1/options/accounts"
    headers = {
        'Authorization': f'Bearer {PAT}',
        'Content-Type': 'application/json',
        'Deriv-App-ID': APP_ID
    }
    res = requests.get(url, headers=headers)
    accounts = res.json().get('data', [])
    demo_acc = next((a for a in accounts if a.get('account_type') == 'demo'), None)
    if not demo_acc:
        return None
    acc_id = demo_acc['account_id']
    url_otp = f"https://api.derivws.com/trading/v1/options/accounts/{acc_id}/otp"
    res2 = requests.post(url_otp, headers=headers)
    return res2.json().get('data', {}).get('url')

async def main():
    uri = get_auth_url()
    if not uri:
        print("Could not get URI")
        return
    
    async with websockets.connect(uri) as ws:
        proposal = {
            "proposal": 1,
            "amount": 10,
            "basis": "stake",
            "contract_type": "ACCU",
            "currency": "USD",
            "growth_rate": 0.05,
            "underlying_symbol": "R_10"
        }
        await ws.send(json.dumps(proposal))
        resp = await ws.recv()
        data = json.loads(resp)
        print("Raw Proposal JSON:")
        print(json.dumps(data, indent=2))

asyncio.run(main())
