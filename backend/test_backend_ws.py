import websockets
import asyncio
import json

async def test():
    uri = 'ws://localhost:8000/ws/market'
    async with websockets.connect(uri) as ws:
        print('Connected to backend WS')
        
        msg = {'type': 'subscribe', 'symbols': ['BTCUSDT']}
        await ws.send(json.dumps(msg))
        
        try:
            for i in range(5):
                resp = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(resp)
                print('Received:', data.get('type'))
        except asyncio.TimeoutError:
            print('Timeout')

asyncio.run(test())