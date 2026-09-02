import websockets
import asyncio
import json

async def test():
    async with websockets.connect('wss://socket.india.delta.exchange') as ws:
        msg = {'type': 'subscribe', 'payload': {'channels': [{'name': 'mark_price', 'symbols': ['BTCUSD', 'ETHUSD']}]}}
        await ws.send(json.dumps(msg))
        print('Sent subscribe')
        
        try:
            for i in range(20):
                resp = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(resp)
                if data.get('type') == 'mark_price':
                    print('Mark price:', data['symbol'], '=', data['price'])
                else:
                    print('Other:', data)
        except asyncio.TimeoutError:
            print('Timeout')

asyncio.run(test())