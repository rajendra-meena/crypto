import httpx
import asyncio

async def check():
    async with httpx.AsyncClient() as client:
        r = await client.get('https://api.india.delta.exchange/v2/products')
        data = r.json()
        for p in data.get('result', []):
            if p.get('contract_type') == 'perpetual_future':
                print(f"{p['symbol']} -> id: {p['id']}")

asyncio.run(check())