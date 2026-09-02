import websockets
import asyncio
import json

async def test():
    uri = 'ws://localhost:8000/ws/market'
    async with websockets.connect(uri, origin='http://localhost:3001') as ws:
        print('Connected to backend WS')
        msg = {'type': 'subscribe', 'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']}
        await ws.send(json.dumps(msg))
        
        try:
            for i in range(20):
                resp = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(resp)
                print('Received:', data.get('type'), 'symbol:', data.get('payload', {}).get('symbol', 'N/A'))
        except asyncio.TimeoutError:
            print('Timeout')

asyncio.run(test())