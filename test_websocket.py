import asyncio
import websockets

async def test_websocket():
    uri = "ws://192.168.0.106/ws"
    try:
        async with websockets.connect(uri) as ws:
            print("Debug: Connesso, invio 'get_encoder_buffer'")
            await ws.send("get_encoder_buffer")
            for _ in range(5):
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    if isinstance(message, str):
                        print(f"Debug: Messaggio testuale: {message[:100]}...")
                    else:
                        print(f"Debug: Messaggio binario di {len(message)} byte")
                except asyncio.TimeoutError:
                    print("Debug: Timeout in attesa di un messaggio")
                    break
                except websockets.exceptions.ConnectionClosed as e:
                    print(f"Debug: Connessione chiusa: {e}")
                    break
    except Exception as e:
        print(f"Debug: Errore: {e}")

asyncio.run(test_websocket())