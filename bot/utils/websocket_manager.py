import asyncio
from io import BytesIO

from PIL import Image
from aiohttp import WSMsgType, ClientSession, ClientConnectionError

from bot.utils import centrifuge, logger


class WebsocketError(Exception):
    """Custom exception for WebSocket errors."""
    pass


class WebSocketClosedError(WebsocketError):
    pass


class WebSocketGeneralError(WebsocketError):
    pass


class WebSocketUnhandledError(WebsocketError):
    pass


class WebsocketManager:
    def __init__(self, http_client: ClientSession, token: str):
        self.websocket = None
        self.payload = None
        self.websocket_url = "wss://notpx.app/connection/websocket"
        self.http_client = http_client
        self.token = token

    async def __generate_payload(self, token):
        auth_data = f'{{"token":"{token}"}}'

        auth_command = [
            {
                "connect": {
                    "data": auth_data.encode(),
                    "name": "js",
                },
                "id": 1,
            }
        ]
        return centrifuge.encode_commands(auth_command)

    async def __get_data(self, max_retries=5):
        for attempt in range(1, max_retries + 1):
            try:
                msg = await self.websocket.receive()
                if msg.type == WSMsgType.BINARY:
                    decoded_data = centrifuge.decode_message(msg.data)
                    if isinstance(decoded_data, bytes):
                        image = Image.open(BytesIO(decoded_data))
                        return image
                    elif msg.type == WSMsgType.TEXT:
                        return decoded_data
                    elif msg.type == WSMsgType.CLOSE:
                        raise WebSocketClosedError(f"WebSocket closed with code: {decoded_data}")
                    elif msg.type == WSMsgType.ERROR:
                        raise WebSocketGeneralError(f"WebSocket error: {decoded_data}")
            except Exception as e:
                if attempt == max_retries:
                    raise WebSocketGeneralError(f"Failed to get data. {e}")
                await asyncio.sleep(1)

    async def get_canvas(self):
        try:
            self.websocket = await self.http_client.ws_connect(
                url=self.websocket_url,
                protocols=["centrifuge-protobuf"],
            )
            self.payload = await self.__generate_payload(self.token)
            await self.websocket.send_bytes(self.payload)

            data = await self.__get_data()
            return data
        except WebSocketClosedError as e:
            raise e
        except WebSocketGeneralError as e:
            raise e
        except WebSocketUnhandledError as e:
            raise e
        except ClientConnectionError as e:
            raise e
        except Exception as e:
            raise e
        finally:
            await self.close_websocket()

    async def paint(self, pixel_id, color):
        try:
            self.websocket = await self.http_client.ws_connect(
                url=self.websocket_url,
                protocols=["centrifuge-protobuf"],
            )
            self.payload = await self.__generate_payload(self.token)

            await self.websocket.send_bytes(self.payload)

            msg = await self.websocket.receive()
            if msg:
                paint_payload = f'''<	j8
                -{{"type":0,"pixelId":{pixel_id},"color":"{color}"}}repaint'''.encode()
                if not self.websocket.closed:
                    await self.websocket.send_bytes(paint_payload)
                else:
                    raise ClientConnectionError("WebSocket connection is closed.")
            else:
                raise

        except ClientConnectionError as e:
            raise e
        except Exception as e:
            raise e
        finally:
            await self.close_websocket()

    async def close_websocket(self):
        if self.websocket:
            await self.websocket.close()
