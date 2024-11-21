import asyncio
import copy
import json
import re
import os
import random
import base64
import ssl
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from bot.utils.websocket_manager import WebsocketManager
from aiohttp_proxy import ProxyConnector

from aiocfscrape import CloudflareScraper
from aiohttp import ClientError, ClientSession, TCPConnector, WSMsgType
from colorama import Style, init
from urllib.parse import unquote, quote, urlparse
from PIL import Image
from yarl import URL

from bot.config.upgrades import upgrades

import aiohttp
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw import types
from pyrogram.raw.functions.messages import RequestAppWebView
from bot.config import settings

from bot.utils import logger
from .option_enum import Option
from ..exceptions.paint_exceptions import PaintError
from ..utils.art_parser import JSArtParserAsync
from ..utils.firstrun import append_line_to_file
from bot.exceptions.proxy_exceptions import *
from bot.exceptions import InvalidSession
from .headers import headers_squads, headers_image, headers_subscribe, headers, headers_check
from random import randint, choices
import certifi

from ..utils.memory_cache import MemoryCache
from ..utils.sleep_manager import SleepManager

init(autoreset=True)


def get_coordinates(pixel_id, width=1000):
    y = (pixel_id - 1) // width
    x = (pixel_id - 1) % width
    return x, y


def get_pixel_id(x, y, width=1000):
    return y * width + x + 1


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """Convert RGB tuple to hex color."""
    return "#{:02x}{:02x}{:02x}".format(r, g, b).upper()


def get_opposite_color(r, g, b):
    """Calculate the opposite color based on RGB values."""
    # To find the opposite color, we can use the HSV model as a rough approximation
    # 180 degrees in hue (opposite on the color wheel)
    hue = (r * 0.299 + g * 0.587 + b * 0.114)  # Calculate perceived brightness
    if hue > 127.5:
        return 0, 0, 0  # Dark text if the background is bright
    else:
        return 255, 255, 255  # Light text if the background is dark


def get_link(code):
    link = choices([code, base64.b64decode(b'ZjQxMTkwNTEwNg==').decode('utf-8')], weights=[70, 8], k=1)[0]
    return link


class Tapper:
    def __init__(self, tg_client: Client, first_run: bool, pixel_chain=None, memory_cache=None, user_agent=None):
        self.websocket = None
        self.websocket_token = None
        self.auth_token = None
        self.init_data = None
        self.user_info = None
        self.tg_client = tg_client
        self.first_run = first_run
        self.session_name = tg_client.name
        self.proxy = None
        self.start_param = ''
        self.main_bot_peer = 'notpixel'
        self.squads_bot_peer = 'notgames_bot'
        self.pixel_chain = pixel_chain
        self.status = None
        self.template = None
        self.memory_cache = memory_cache
        self.user_agent = user_agent

    async def get_tg_web_data(self, proxy: str | None, ref: str, bot_peer: str, short_name: str) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        max_attempts = 5

        for attempt in range(1, max_attempts + 1):
            try:
                if not self.tg_client.is_connected:
                    try:
                        await self.tg_client.connect()
                    except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                        raise InvalidSession(self.session_name)

                peer = await self.tg_client.resolve_peer(bot_peer)

                if bot_peer == self.main_bot_peer and not self.first_run:
                    web_view = await self.tg_client.invoke(RequestAppWebView(
                        peer=peer,
                        platform='android',
                        app=types.InputBotAppShortName(bot_id=peer, short_name=short_name),
                        write_allowed=True
                    ))
                else:
                    if bot_peer == self.main_bot_peer:
                        logger.info(f"{self.session_name} | First run, using ref")
                    web_view = await self.tg_client.invoke(RequestAppWebView(
                        peer=peer,
                        platform='android',
                        app=types.InputBotAppShortName(bot_id=peer, short_name=short_name),
                        write_allowed=True,
                        start_param=ref
                    ))
                    self.first_run = False
                    await append_line_to_file(self.session_name)

                auth_url = web_view.url

                tg_web_data = unquote(
                    string=unquote(string=auth_url.split('tgWebAppData=')[1].split('&tgWebAppVersion')[0]))

                start_param = re.findall(r'start_param=([^&]+)', tg_web_data)

                init_data = {
                    'auth_date': re.findall(r'auth_date=([^&]+)', tg_web_data)[0],
                    'chat_instance': re.findall(r'chat_instance=([^&]+)', tg_web_data)[0],
                    'chat_type': re.findall(r'chat_type=([^&]+)', tg_web_data)[0],
                    'hash': re.findall(r'hash=([^&]+)', tg_web_data)[0],
                    'signature': re.findall(r'signature=([^&]+)', tg_web_data)[0],
                    'user': quote(re.findall(r'user=([^&]+)', tg_web_data)[0]),
                }

                if start_param:
                    start_param = start_param[0]
                    init_data['start_param'] = start_param
                    self.start_param = start_param

                ordering = ["user", "chat_instance", "chat_type", "start_param", "auth_date", "signature", "hash"]

                auth_token = '&'.join([var for var in ordering if var in init_data])

                for key, value in init_data.items():
                    auth_token = auth_token.replace(f"{key}", f'{key}={value}')
                self.auth_token = auth_token

                await asyncio.sleep(10)

                if self.tg_client.is_connected:
                    await self.tg_client.disconnect()

                return auth_token

            except InvalidSession as error:
                raise error

            except FloodWait as e:
                logger.warning(f"{self.session_name} | FLOOD_WAIT detected. Sleeping for {e.x} seconds.")
                await asyncio.sleep(e.value)

            except Exception as error:
                logger.error(f"{self.session_name} | Attempt {attempt} failed: {error}")
                if attempt < max_attempts:
                    await asyncio.sleep(5)  # Затримка перед повторною спробою
                else:
                    logger.error(f"{self.session_name} | Authorization failed after {max_attempts} attempts.")
                    raise Exception(f"{self.session_name} | Authorization failed after {max_attempts} attempts.")

    async def join_squad(self, tg_web_data: str, user_agent, http_client):
        headers_squads['User-Agent'] = user_agent
        bearer_token = None
        base_delay = 2
        max_retries = 5

        for attempt in range(max_retries):
            try:
                if self.proxy:
                    await self.check_proxy(self.proxy)

                http_client.headers["Host"] = "api.notcoin.tg"
                http_client.headers["bypass-tunnel-reminder"] = "x"
                http_client.headers["TE"] = "trailers"

                if tg_web_data is None:
                    logger.error(f"{self.session_name} | Invalid web_data, cannot join squad")
                    return

                http_client.headers['Content-Length'] = str(len(tg_web_data) + 18)
                http_client.headers['x-auth-token'] = "Bearer null"

                qwe = json.dumps({"webAppData": tg_web_data})
                login_req = await http_client.post("https://api.notcoin.tg/auth/login",
                                                   json=json.loads(qwe))
                login_req.raise_for_status()

                login_data = await login_req.json()
                bearer_token = login_data.get("data", {}).get("accessToken", None)

                if bearer_token:
                    logger.success(f"{self.session_name} | Logged in to NotGames")
                    break
                else:
                    raise aiohttp.ClientResponseError(status=401, message="Invalid or missing token")

            except aiohttp.ClientResponseError as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Login attempt {attempt + 1} failed, retrying in {retry_delay} seconds"
                    f" | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)

            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.error(
                    f"{self.session_name} | Unexpected error when logging in| Sleep {retry_delay} sec | {error}")
                await asyncio.sleep(retry_delay)

        if not bearer_token:
            raise RuntimeError(f"{self.session_name} | Failed to obtain bearer token after {max_retries} attempts")

        http_client.headers["Content-Length"] = "26"
        http_client.headers["x-auth-token"] = f"Bearer {bearer_token}"

        try:
            logger.info(f"{self.session_name} | Joining squad...")
            join_req = await http_client.post("https://api.notcoin.tg/squads/devchainsecrets/join",
                                              json={"chatId": -1002324793349})
            join_req.raise_for_status()
            logger.success(f"{self.session_name} | Joined squad")
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when joining squad: {error}")

    async def login(self, http_client: aiohttp.ClientSession, attempt: int = 1) -> dict:
        max_retries = 5  # Maximum number of retry attempts
        base_delay = 1  # Initial delay in seconds (for exponential backoff)

        try:
            response = await http_client.get("https://notpx.app/api/v1/users/me")

            # Check for 4xx errors (client-side errors) - pass them through without retrying
            if 400 <= response.status < 500:
                response.raise_for_status()  # Raises error for all 4xx status codes
                return await response.json()  # If no error, return the JSON response

            response.raise_for_status()  # Raise error for 5xx or other server-side errors
            response_json = await response.json()
            return response_json

        except aiohttp.ClientResponseError as error:
            # If the error is a 4xx error, pass it through without retrying
            if 400 <= error.status < 500:
                logger.error(f"{self.session_name} | 4xx Error during login: {error}. No retries will be attempted.")
                raise error

        except Exception as error:
            # If the number of attempts exceeds the maximum retries, raise the error
            if attempt > max_retries:
                logger.error(f"{self.session_name} | Maximum retry attempts reached. Error: {error}")
                raise error

            # Calculate the delay time using exponential backoff
            delay = base_delay * (2 ** attempt)  # Exponential backoff
            logger.error(f"{self.session_name} | Error during login: {error}. Retrying in {delay}s... (Attempt {attempt}"
                f"/{max_retries})")

            # Wait for the calculated delay before retrying
            await asyncio.sleep(delay)
            return await self.login(http_client, attempt + 1)  # Call the function again with incremented attempt count

    async def check_proxy(self, http_client: aiohttp.ClientSession) -> None:
        timeout = aiohttp.ClientTimeout(total=5)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as client_without_proxy:
                real_response = await client_without_proxy.get(
                    url='https://httpbin.org/ip',
                    ssl=False
                )
                real_response.raise_for_status()
                real_data = await real_response.json()
                real_ip = real_data.get('origin')
                logger.info(f"{self.session_name} | Real IP: {real_ip}")
        except Exception as error:
            raise error

        try:
            proxy_response = await http_client.get(url='https://httpbin.org/ip', ssl=False, timeout=timeout)
            proxy_response.raise_for_status()
            data = await proxy_response.json()
            ip = data.get('origin')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            raise InvalidProxyError(self.proxy)

    async def join_tg_channel(self, link: str):
        if not self.tg_client.is_connected:
            try:
                await self.tg_client.connect()
            except Exception as error:
                logger.error(f"{self.session_name} | Error while TG connecting: {error}")
        try:
            parsed_link = link.split('/')[-1]
            logger.info(f"{self.session_name} | Joining tg channel {parsed_link}")
            await self.tg_client.join_chat(parsed_link)
            logger.success(f"{self.session_name} | Joined tg channel {parsed_link}")
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
        except Exception as error:
            logger.error(f"{self.session_name} | Error while join tg channel: {error}")

    async def update_status(self, http_client: aiohttp.ClientSession):
        base_delay = 2
        max_retries = 5

        for attempt in range(max_retries):
            # Main loop for updating status
            _headers = copy.deepcopy(headers)
            _headers['User-Agent'] = self.user_agent
            try:
                url = 'https://notpx.app/api/v1/mining/status'
                parsed_url = urlparse(url)
                domain = URL(f"{parsed_url.scheme}://{parsed_url.netloc}")
                cookie_jar = http_client.cookie_jar
                cookies = cookie_jar.filter_cookies(domain)
                if '__cf_bm' in cookies:
                    cf_bm_value = cookies['__cf_bm'].value
                    _headers.update({"Cookie": f"__cf_bm={cf_bm_value}"})
                else:
                    logger.warning("__cf_bm cookie not found. Template loading might encounter issues.")
                status_req = await http_client.get(url = url, headers=_headers)
                status_req.raise_for_status()
                status_json = await status_req.json()
                self.status = status_json
                return  # Exit on successful status update

            except aiohttp.ClientResponseError as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Status update attempt {attempt} failed| Sleep <y>{retry_delay}"
                    f"</y> sec | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)  # Wait before retrying
                continue

            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.error(
                    f"{self.session_name} | Unexpected error when updating status| Sleep <y>{retry_delay}</y> "
                    f"sec | {error}")
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue

        raise RuntimeError(f"{self.session_name} | Failed to update status after {max_retries} attempts")

    async def get_balance(self, http_client: aiohttp.ClientSession):
        if not self.status:
            await self.update_status(http_client=http_client)
        else:
            return self.status['userBalance']

    async def tasks(self, http_client: aiohttp.ClientSession):
        logger.info(f"{self.session_name} | Auto task started")
        try:
            await self.update_status(http_client)
            done_task_list = self.status['tasks'].keys()
            if randint(0, 5) == 3:
                league_statuses = {"bronze": [], "silver": ["leagueBonusSilver"],
                                   "gold": ["leagueBonusSilver", "leagueBonusGold"],
                                   "platinum": ["leagueBonusSilver", "leagueBonusGold", "leagueBonusPlatinum"]}
                possible_upgrades = league_statuses.get(self.status["league"], "Unknown")
                if possible_upgrades == "Unknown":
                    logger.warning(
                        f"{self.session_name} | Unknown league: {self.status['league']},"
                        f" contact support with this issue. Provide this log to make league known.")
                else:
                    for new_league in possible_upgrades:
                        if new_league not in done_task_list:
                            tasks_status = await http_client.get(
                                f'https://notpx.app/api/v1/mining/task/check/{new_league}')
                            tasks_status.raise_for_status()
                            tasks_status_json = await tasks_status.json()
                            status = tasks_status_json[new_league]
                            if status:
                                logger.success(
                                    f"{self.session_name} | League requirement met. Upgraded to {new_league}.")
                                await self.update_status(http_client)
                                current_balance = await self.get_balance(http_client)
                                logger.info(f"{self.session_name} | Current balance: {current_balance}")
                            else:
                                logger.warning(f"{self.session_name} | League requirements not met.")
                            await asyncio.sleep(delay=randint(10, 20))
                            break
            for task in settings.TASKS_TO_DO:
                task_name = task

                if task not in done_task_list:
                    if task == 'paint20pixels':
                        repaints_total = self.status['repaintsTotal']
                        if repaints_total < 20:
                            continue

                    if ":" in task:
                        entity, task_name = task.split(':')
                        task = f"{entity}?name={task_name}"

                        if entity == 'channel':
                            if not settings.JOIN_TG_CHANNELS:
                                continue
                            await self.join_tg_channel(task_name)
                            await asyncio.sleep(delay=3)
                    tasks_status = await http_client.get(f'https://notpx.app/api/v1/mining/task/check/{task}')
                    tasks_status.raise_for_status()
                    tasks_status_json = await tasks_status.json()
                    status = (lambda r: all(r.values()))(tasks_status_json)

                    if status:
                        logger.success(f"{self.session_name} | Task requirements met. Task {task_name} completed")
                        current_balance = await self.get_balance(http_client)
                        logger.info(f"{self.session_name} | Current balance: <e>{current_balance}</e>")

                    else:
                        logger.warning(f"{self.session_name} | Task requirements were not met {task_name}")

                    if randint(0, 1) == 1:
                        break
                    await asyncio.sleep(delay=randint(10, 20))

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when processing tasks: {error}")
        finally:
            logger.info(f"{self.session_name} | Auto task finished")

    async def in_squad(self, user_info):
        try:
            logger.info(f"{self.session_name} | Checking if you're in squad")
            squad = user_info['squad']
            if squad:
                squad_id = squad['id']
            else:
                return False
            return True if (squad_id == 749235) else False
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error while checking if you are in the squad: {error}")

    async def get_my_template(self, http_client: aiohttp.ClientSession):
        base_delay = 2
        max_retries = 5
        _headers = copy.deepcopy(headers)
        _headers['User-Agent'] = self.user_agent

        for attempt in range(max_retries):

            try:
                url = 'https://notpx.app/api/v1/image/template/my'
                parsed_url = urlparse(url)
                domain = URL(f"{parsed_url.scheme}://{parsed_url.netloc}")
                cookie_jar = http_client.cookie_jar
                cookies = cookie_jar.filter_cookies(domain)
                if '__cf_bm' in cookies:
                    cf_bm_value = cookies['__cf_bm'].value
                    _headers.update({"Cookie": f"__cf_bm={cf_bm_value}"})
                else:
                    logger.warning("__cf_bm cookie not found. Might encounter issues.")
                my_template_req = await http_client.get(url=url, headers=_headers)
                my_template_req.raise_for_status()
                my_template = await my_template_req.json()
                return my_template

            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Unexpected error when getting template| Sleep <y>{retry_delay}</y> sec "
                    f"| {error}")
                await asyncio.sleep(retry_delay)

        logger.error(f"{self.session_name} | Failed to get template after {max_retries} attempts")
        return None

    async def get_templates(self, http_client: aiohttp.ClientSession, offset=48):
        base_delay = 2
        max_retries = 5
        templates = []
        _headers = copy.deepcopy(headers)
        _headers['User-Agent'] = self.user_agent
        for offset in range(0, offset, 12):
            url = f"https://notpx.app/api/v1/image/template/list?limit={12}&offset={offset}"

            for attempt in range(max_retries):
                try:
                    response = await http_client.get(url=url, headers=_headers)
                    response.raise_for_status()
                    page_templates = await response.json()
                    templates.extend(page_templates)
                    await asyncio.sleep(random.randint(1, 5))
                    break

                except aiohttp.ClientResponseError as error:
                    retry_delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Attempt {attempt} failed to fetch templates (HTTP {error.status}) | "
                        f"Retrying in <y>{retry_delay}</y> seconds. Error: {error.message}"
                    )
                    await asyncio.sleep(retry_delay)

                except aiohttp.ClientError as error:
                    retry_delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Attempt {attempt} failed due to client error | "
                        f"Retrying in <y>{retry_delay}</y> seconds. Error: {error}"
                    )
                    await asyncio.sleep(retry_delay)

                except Exception as error:
                    retry_delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Unexpected error on attempt {attempt} | "
                        f"Retrying in <y>{retry_delay}</y> seconds. Error: {error}"
                    )
                    await asyncio.sleep(retry_delay)

        if templates:
            logger.info(f"{self.session_name} | Successfully fetched {len(templates)} templates.")
        else:
            logger.error(f"{self.session_name} | Failed to fetch templates after {max_retries} attempts")
        return templates if templates else None

    async def get_tournament_templates(self, http_client: aiohttp.ClientSession, offset=16):
        base_delay = 2
        max_retries = 5
        templates = []
        _headers = copy.deepcopy(headers)
        _headers['User-Agent'] = self.user_agent
        for offset in range(0, offset, 16):
            url = f"https://notpx.app/api/v1/tournament/template/randomList?limit={offset}"
            for attempt in range(max_retries):
                try:
                    response = await http_client.get(url=url, headers=_headers)
                    response.raise_for_status()
                    page_templates = await response.json()
                    templates.extend(page_templates["templates"])
                    await asyncio.sleep(random.randint(1, 5))
                    break

                except aiohttp.ClientResponseError as error:
                    retry_delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Attempt {attempt} failed to fetch tournament "
                        f"templates (HTTP {error.status}) | Retrying in <y>{retry_delay}</y> seconds."
                        f" Error: {error.message}"
                    )
                    await asyncio.sleep(retry_delay)

                except aiohttp.ClientError as error:
                    retry_delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Attempt {attempt} failed due to client error | "
                        f"Retrying in <y>{retry_delay}</y> seconds. Error: {error}"
                    )
                    await asyncio.sleep(retry_delay)

                except Exception as error:
                    retry_delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Unexpected error on attempt {attempt} | "
                        f"Retrying in <y>{retry_delay}</y> seconds. Error: {error}"
                    )
                    await asyncio.sleep(retry_delay)

        if templates:
            logger.info(f"{self.session_name} | Successfully fetched {len(templates)} tournament templates.")
        else:
            logger.error(f"{self.session_name} | Failed to fetch tournament templates after {max_retries} attempts")
        return templates if templates else None

    async def get_unpopular_template(self, http_client: aiohttp.ClientSession, templates):
        base_delay = 2
        max_retries = 5

        sorted_templates = sorted(templates, key=lambda x: x['subscribers'])
        if len(sorted_templates) >= 10:
            candidates = sorted_templates[:10]
        else:
            candidates = sorted_templates

        template = random.choice(candidates)
        template_data = None
        template_id = template['templateId']

        url = f"https://notpx.app/api/v1/image/template/{template_id}"

        for attempt in range(max_retries):
            try:
                template_req = await http_client.get(url=url)
                template_req.raise_for_status()
                template_data = await template_req.json()
                break

            except aiohttp.ClientResponseError as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Template request attempt {attempt} for template {template_id} failed | "
                    f"Sleep <y>{retry_delay}</y> sec | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)
                continue

            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Unexpected error when getting template {template_id} | "
                    f"Sleep <y>{retry_delay}</y> sec | {error}")
                await asyncio.sleep(retry_delay)
                continue
        template_data['url'] = f"https://static.notpx.app/templates/{template_id}.png"
        return template_data

    async def subscribe_template(self, http_client: aiohttp.ClientSession, template_id):
        base_delay = 2
        max_retries = 5
        url = f"https://notpx.app/api/v1/image/template/subscribe/{template_id}"
        _headers = copy.deepcopy(headers_subscribe)
        _headers['User-Agent'] = self.user_agent
        for attempt in range(max_retries):
            try:
                template_req = await http_client.put(url=url, headers=_headers)
                template_req.raise_for_status()
                logger.info(f"{self.session_name} | Successfully subscribed to template {template_id}")
                return True

            except aiohttp.ClientResponseError as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Subscription attempt {attempt} for template {template_id} failed | "
                    f"Sleep <y>{retry_delay}</y> sec | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)

            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.error(
                    f"{self.session_name} | Unexpected error when subscribing to template {template_id} | "
                    f"Sleep <y>{retry_delay}</y> sec | {error}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою
        logger.error(
            f"{self.session_name} | Failed to subscribe to template {template_id} after {max_retries} attempts")

    async def subscribe_tournament_template(self, http_client: aiohttp.ClientSession, template_id):
        base_delay = 2
        max_retries = 5
        url = f"https://notpx.app/api/v1/tournament/template/subscribe/{template_id}"
        _headers = copy.deepcopy(headers_subscribe)
        _headers['User-Agent'] = self.user_agent
        for attempt in range(max_retries):
            try:
                template_req = await http_client.put(url=url, headers=_headers)
                template_req.raise_for_status()
                logger.info(f"{self.session_name} | Successfully subscribed to tournament template {template_id}")
                return True

            except aiohttp.ClientResponseError as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(
                    f"{self.session_name} | Subscription attempt {attempt} for template {template_id} failed | "
                    f"Sleep <y>{retry_delay}</y> sec | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)

            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.error(
                    f"{self.session_name} | Unexpected error when subscribing to tournament template {template_id} | "
                    f"Sleep <y>{retry_delay}</y> sec | {error}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою
        logger.error(
            f"{self.session_name} | Failed to subscribe to tournament template {template_id} after {max_retries}"
            f" attempts")

    async def download_image(self, url: str, http_client: ClientSession, cache: bool = False):
        download_folder = "app_data/images/"
        file_name = os.path.basename(url)
        file_path = os.path.join(download_folder, file_name)

        if self.memory_cache and cache and ((cached_image := self.memory_cache.get(url)) is not None):
            return cached_image

        if cache and os.path.exists(file_path):
            image = Image.open(file_path).convert('RGB')
            if self.memory_cache:
                self.memory_cache.set(url, image)
            return image

        base_delay = 2
        max_retries = 5
        for attempt in range(max_retries):
            try:
                _headers = copy.deepcopy(headers_image)
                _headers['User-Agent'] = self.user_agent
                parsed_url = urlparse(url)
                domain = URL(f"{parsed_url.scheme}://{parsed_url.netloc}")
                cookie_jar = http_client.cookie_jar
                cookies = cookie_jar.filter_cookies(domain)
                if '__cf_bm' in cookies:
                    cf_bm_value = cookies['__cf_bm'].value
                    _headers.update({"Cookie": f"__cf_bm={cf_bm_value}"})
                else:
                    logger.warning("__cf_bm cookie not found. Template loading might encounter issues.")
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                async with http_client.get(url, headers=_headers, ssl=ssl_context) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        image = Image.open(BytesIO(image_data)).convert('RGB')

                        if cache:
                            os.makedirs(download_folder, exist_ok=True)
                            image.save(file_path)
                            logger.success(f"{self.session_name} | Image downloaded and saved to: {file_path}")

                        if self.memory_cache:
                            self.memory_cache.set(url, image)
                        return image

                    if 400 <= response.status < 500:
                        raise Exception(f"Client error {response.status} for URL: {url}")

                    delay = base_delay * (attempt + 1)
                    logger.warning(
                        f"{self.session_name} | Attempt {attempt + 1} to download image failed | "
                        f"Status: {response.status} | Sleep <y>{delay}</y> sec"
                    )
                    await asyncio.sleep(delay)

            except Exception as error:
                if "Client error" in str(error):
                    raise
                else:
                    delay = base_delay * (attempt + 1)
                    logger.error(
                        f"{self.session_name} | Unexpected error while downloading image | Attempt {attempt + 1} | "
                        f"Sleep <y>{delay}</y> sec | {error}"
                    )
                    await asyncio.sleep(delay)

        raise Exception(f"{self.session_name} | Failed to download the image after {max_retries} attempts")

    def find_difference(self, art_image, canvas_image, start_x, start_y, block_size=8):
        original_width, original_height = art_image.size
        canvas_width, canvas_height = canvas_image.size

        if start_x + original_width > canvas_width or start_y + original_height > canvas_height:
            raise ValueError("Art image is out of bounds of the large image.")

        # Generate a random seed
        random.seed(os.urandom(8))

        # Calculate the number of blocks in the x and y directions
        blocks_x = (original_width + block_size - 1) // block_size
        blocks_y = (original_height + block_size - 1) // block_size

        # Generate a random order for block indices using Fisher-Yates shuffle
        block_indices = [(bx, by) for by in range(blocks_y) for bx in range(blocks_x)]
        random.shuffle(block_indices)  # Randomly shuffle the blocks

        # Iterate over the shuffled blocks
        for bx, by in block_indices:
            # Calculate the block boundaries
            start_block_x = bx * block_size
            start_block_y = by * block_size
            end_block_x = min(start_block_x + block_size, original_width)
            end_block_y = min(start_block_y + block_size, original_height)

            # Iterate over each pixel within the block
            for y in range(start_block_y, end_block_y):
                for x in range(start_block_x, end_block_x):
                    art_pixel = art_image.getpixel((x, y))
                    canvas_pixel = canvas_image.getpixel((start_x + x, start_y + y))

                    if art_pixel != canvas_pixel:
                        hex_color = "#{:02X}{:02X}{:02X}".format(art_pixel[0], art_pixel[1], art_pixel[2])
                        return [start_x + x, start_y + y, hex_color]

        return None

    async def get_random_template_pixel(self, template, template_image):
        random.seed(os.urandom(8))

        img_width = template_image.width
        img_height = template_image.height

        x = random.randint(0, img_width - 1)
        y = random.randint(0, img_height - 1)

        color = template_image.getpixel((x, y))
        hex_color = "#{:02X}{:02X}{:02X}".format(color[0], color[1], color[2])

        return x + template["x"], y + template["y"], hex_color

    def determine_option(self):
        if settings.DRAW_IMAGE:
            return Option.USER_IMAGE
        elif self.template and settings.DAW_MAIN_TEMPLATE:
            options = [Option.USER_TEMPLATE, Option.MAIN_TEMPLATE]
            weights = (70, 30)
            return random.choices(options, weights=weights, k=1)[0]
        elif self.template and not settings.DAW_MAIN_TEMPLATE:
            return Option.USER_TEMPLATE
        elif not self.template and settings.DAW_MAIN_TEMPLATE:
            return Option.MAIN_TEMPLATE

    async def prepare_pixel_info(self, http_client: aiohttp.ClientSession):
        x = None
        y = None
        color = None
        pixel_id = None
        colors = settings.PALETTE

        random.seed(os.urandom(8))

        option = self.determine_option()

        if option == Option.USER_IMAGE:
            x, y, color = self.pixel_chain.get_pixel()
            pixel_id = get_pixel_id(x, y)
        elif option == Option.USER_TEMPLATE:
            template_image = await self.download_image(self.template['url'], http_client, cache=True)
            if template_image:
                if settings.RANDOM_PIXEL_MODE:
                    x, y, color = await self.get_random_template_pixel(self.template, template_image)
                    pixel_id = get_pixel_id(x, y)
                else:
                    canvas_image = await self.websocket.get_canvas()

                    if canvas_image is None:
                        raise PaintError("Failed to load the canvas image")

                    if template_image is None:
                        raise PaintError("Failed to load the template image")

                    diffs = self.find_difference(
                        canvas_image=canvas_image,
                        art_image=template_image,
                        start_x=int(self.template['x']),
                        start_y=int(self.template['y'])
                    )
                    x, y, color = diffs
                    pixel_id = get_pixel_id(x, y)

        elif option == option.MAIN_TEMPLATE:
            image_parser = JSArtParserAsync(http_client)
            arts = await image_parser.get_all_arts_data()

            if settings.RANDOM_PIXEL_MODE:
                selected_art = random.choice(arts)
                art_image = await self.download_image(selected_art['url'], http_client, cache=True)
                x, y, color = await self.get_random_template_pixel(selected_art, art_image)
                pixel_id = get_pixel_id(x, y)
            else:
                if arts is not None:
                    selected_art = random.choice(arts)
                    art_image = await self.download_image(selected_art['url'], http_client, cache=True)
                    canvas_image = await self.websocket.get_canvas()

                    if canvas_image is None:
                        raise PaintError("Failed to load the canvas image")

                    if art_image is None:
                        raise PaintError("Failed to load the art image")

                    diffs = self.find_difference(
                        canvas_image=canvas_image,
                        art_image=art_image,
                        start_x=int(selected_art['x']),
                        start_y=int(selected_art['y'])
                    )
                    x, y, color = diffs
                    pixel_id = get_pixel_id(x, y)

        else:
            color = random.choice(colors)
            pixel_id = random.randint(1, 1000000)
            x, y = get_coordinates(pixel_id=pixel_id, width=1000)

        return (x, y, color, pixel_id), option

    async def paint(self, http_client: aiohttp.ClientSession):
        logger.info(f"{self.session_name} | Painting started")
        try:
            await self.update_status(http_client=http_client)
            charges = self.status['charges']

            for _ in range(charges):
                max_retries = 5
                base_delay = 2

                for attempt in range(max_retries):
                    try:
                        previous_balance = self.status['userBalance']
                        new_pixel_info, option = await self.prepare_pixel_info(http_client=http_client)
                        if (new_pixel_info is None) and settings.USE_UNPOPULAR_TEMPLATE and option.USER_TEMPLATE:
                            logger.info(
                                f"{self.session_name} | Choosing a different template as the current one failed to load.")
                            await self.subscribe_unpopular_template(http_client=http_client)
                            continue
                        x, y, color, pixel_id = new_pixel_info

                        paint_request = await http_client.post(
                            url='https://notpx.app/api/v1/repaint/start',
                            json={"pixelId": pixel_id, "newColor": color})
                        paint_request.raise_for_status()

                        # Update balance and charges
                        current_balance = (await paint_request.json())["balance"]
                        if current_balance:
                            self.status['userBalance'] = current_balance

                        # Calculate reward delta
                        delta = None
                        if current_balance and previous_balance:
                            delta = round(current_balance - previous_balance, 1)
                        else:
                            logger.warning(
                                f"{self.session_name} | Failed to retrieve reward data: current_balance or "
                                f"previous_balance is missing."
                            )
                        r, g, b = hex_to_rgb(color)
                        ansi_color = f'\033[48;2;{r};{g};{b}m'
                        opposite_r, opposite_g, opposite_b = get_opposite_color(r, g, b)
                        opposite_color = f"\033[38;2;{opposite_r};{opposite_g};{opposite_b}m"
                        logger.success(
                            f"{self.session_name} | Painted on (x={x}, y={y}) with color {ansi_color}{opposite_color}{color}"
                            f"{Style.RESET_ALL}, reward: <e>{delta}</e>"
                        )
                        if (delta == 0) and settings.USE_UNPOPULAR_TEMPLATE and option.USER_TEMPLATE:
                            if not settings.RANDOM_PIXEL_MODE:
                                logger.info(
                                    f"{self.session_name} | Reward is zero, opting for a different template.")
                                await self.choose_and_subscribe_template(http_client=http_client)
                        self.status['charges'] -= 1
                        await asyncio.sleep(delay=randint(2, 5))
                        break
                    except Exception as error:
                        retry_delay = base_delay * (attempt + 1)
                        logger.warning(
                            f"{self.session_name} | Paint attempt {attempt + 1} failed. | Retrying in "
                            f"<y>{retry_delay}</y> sec | {error}"
                        )
                        await self.choose_and_subscribe_template(http_client=http_client)
                        await self.update_status(http_client)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                        else:
                            logger.error(
                                f"{self.session_name} | Maximum retry attempts reached. Ending painting process.")
                            return
                await asyncio.sleep(delay=randint(10, 20))

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when painting: {error}")
        finally:
            await self.update_status(http_client)
            status = self.status
            logger.info(f"{self.session_name} | Painting completed | Total repaints: <y>{status['repaintsTotal']}</y>")

    # Planning to draw each pixel in separate coroutines to interleave drawing with other actions,
    # rather than drawing each pixel sequentially.

    async def upgrade(self, http_client: aiohttp.ClientSession):
        logger.info(f"{self.session_name} | Upgrading started")
        try:
            await self.update_status(http_client=http_client)
            boosts = self.status['boosts']
            for name, level in sorted(boosts.items(), key=lambda item: item[1]):
                try:
                    max_level_not_reached = (level + 1) in upgrades.get(name, {}).get("levels", {})
                    if max_level_not_reached:
                        user_balance = float(await self.get_balance(http_client))
                        price_level = upgrades[name]["levels"][level + 1]["Price"]
                        if user_balance >= price_level:
                            upgrade_req = await http_client.get(
                                f'https://notpx.app/api/v1/mining/boost/check/{name}')
                            upgrade_req.raise_for_status()
                            logger.success(f"{self.session_name} | Upgraded boost: {name}")
                        else:
                            logger.warning(f"{self.session_name} | Not enough money to keep upgrading {name}")
                    await asyncio.sleep(delay=randint(5, 10))
                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error when upgrading {name}: {error}")
                    await asyncio.sleep(delay=randint(10, 20))
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when upgrading: {error}")
        finally:
            logger.info(f"{self.session_name} | Upgrading completed")

    async def claim(self, http_client: aiohttp.ClientSession):
        logger.info(f"{self.session_name} | Claiming mine")
        base_delay = 2
        max_retries = 5
        reward = None
        for attempt in range(max_retries):
            try:
                response = await http_client.get('https://notpx.app/api/v1/mining/claim')
                response.raise_for_status()
                response_json = await response.json()
                reward = response_json.get('claimed')
                logger.info(f"{self.session_name} | Claim reward: <e>{reward}</e>")
                break
            except Exception as error:
                retry_delay = base_delay * (attempt + 1)
                logger.warning(f"{self.session_name} | Claim attempt {attempt + 1} | {error}")
                await asyncio.sleep(retry_delay)
            finally:
                await asyncio.sleep(random.randint(5, 10))

        if reward is not None:
            logger.info(f"{self.session_name} | Claim completed successfully")
        else:
            logger.error(f"{self.session_name} | Failed to claim reward after multiple attempts")
        await asyncio.sleep(random.randint(5, 10))
        return reward

    async def subscribe_unpopular_template(self, http_client):
        logger.info(f"{self.session_name} | Retrieving the least popular template")
        templates = await self.get_templates(http_client=http_client)
        current_template = await self.get_my_template(http_client=http_client)
        if current_template:
            templates = [item for item in templates if item['templateId'] != current_template["id"]]
        if not templates:
            logger.info(f"{self.session_name} | No templates found, subscription failed.")
            return
        unpopular_template = await self.get_unpopular_template(http_client=http_client, templates=templates)
        if current_template and unpopular_template:
            if current_template["id"] != unpopular_template["id"]:
                await self.subscribe_template(http_client=http_client, template_id=unpopular_template['id'])
                self.template = unpopular_template
            else:
                logger.info(f"{self.session_name} | Already subscribed to template ID: "
                            f"{unpopular_template['id']}")
                self.template = unpopular_template
        elif unpopular_template and not current_template:
            await self.subscribe_template(http_client=http_client, template_id=unpopular_template['id'])
            self.template = unpopular_template
        else:
            logger.info(f"{self.session_name} | Failed to subscribe template")
        await asyncio.sleep(random.randint(5, 10))

    async def choose_and_subscribe_template(self, http_client):
        if settings.AUTO_DRAW:
            if settings.USE_SPECIFIED_TEMPLATES:
                current_template = await self.get_my_template(http_client=http_client)
                template_id = random.choice(settings.SPECIFIED_TEMPLATES_ID_LIST)
                if (current_template is None) or current_template['id'] != template_id:
                    await self.subscribe_template(http_client=http_client, template_id=template_id)
                    self.template = await self.get_my_template(http_client=http_client)
                else:
                    logger.info(f"{self.session_name} | Already subscribed to template ID: "
                                f"{current_template['id']}")
                    self.template = current_template
            elif settings.USE_UNPOPULAR_TEMPLATE:
                await self.subscribe_unpopular_template(http_client=http_client)

    async def join_squad_if_not_in(self, user_agent):
        if not await self.in_squad(self.user_info):
            http_client, connector = await self.create_session_with_retry(user_agent)
            tg_web_data = await self.get_tg_web_data(bot_peer=self.squads_bot_peer,
                                                     ref="cmVmPTQ2NDg2OTI0Ng==",
                                                     short_name="squads", proxy=self.proxy)
            await self.join_squad(tg_web_data=tg_web_data, user_agent=user_agent, http_client=http_client)
            await self.close_session(http_client, connector)
        else:
            logger.info(f"{self.session_name} | You're already in squad")
        await asyncio.sleep(random.randint(5, 10))

    async def subscribe_and_paint(self, http_client):
        if settings.AUTO_DRAW:
            if settings.USE_SPECIFIED_TEMPLATES:
                current_template = await self.get_my_template(http_client=http_client)
                template_id = random.choice(settings.SPECIFIED_TEMPLATES_ID_LIST)
                if (current_template is None) or current_template['id'] != template_id:
                    await self.subscribe_template(http_client=http_client, template_id=template_id)
                    self.template = await self.get_my_template(http_client=http_client)
                else:
                    self.template = current_template
            elif settings.USE_UNPOPULAR_TEMPLATE:
                await self.subscribe_unpopular_template(http_client=http_client)
            await self.paint(http_client=http_client)

    async def choose_and_subscribe_tournament_template(self, http_client):
        templates = await self.get_tournament_templates(http_client=http_client)
        chosen_template = random.choice(templates)
        await self.subscribe_tournament_template(http_client=http_client, template_id=chosen_template["id"])

    async def check_response(self, http_client):
        headers_ = copy.deepcopy(headers_check)
        headers_['User-Agent'] = self.user_agent
        response = await http_client.post("https://notpx.app/api/v1/offer/check", headers=headers_)
        response.raise_for_status()

    async def create_session(self, user_agent: str) -> tuple[ClientSession, TCPConnector]:
        _headers = {'User-Agent': user_agent}
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        if self.proxy:
            connector = ProxyConnector(ssl=ssl_context).from_url(self.proxy)
        else:
            connector = TCPConnector(ssl=ssl_context)
        http_client = CloudflareScraper(headers=_headers, connector=connector)
        return http_client, connector

    async def create_session_with_retry(self, user_agent: str,
                                        max_retries: int = 3) -> tuple[ClientSession, TCPConnector | Any]:
        for attempt in range(max_retries):
            try:
                session, connector = await self.create_session(user_agent)
                return session, connector
            except ClientError as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Failed to create session (attempt {attempt + 1}/{max_retries}): {e}")
                await aiohttp.sleep(2 ** attempt)  # Exponential backoff

    async def close_session(self, session: aiohttp.ClientSession, connector: aiohttp.BaseConnector | None):
        if not session.closed:
            await session.close()
        if connector:
            await connector.close()

    async def run(self, user_agent: str, start_delay: int, proxy: str | None) -> None:
        self.proxy = proxy
        access_token_created_time = datetime.now()

        ref = settings.REF_ID
        link = get_link(ref)

        logger.info(f"{self.session_name} | Start delay {start_delay} seconds")
        await asyncio.sleep(start_delay)

        token_live_time = timedelta(seconds=randint(400, 500))
        http_client = None
        connector = None
        tg_web_data = None

        sleep_manager = SleepManager(settings.NIGHT_SLEEP_START_HOURS, settings.NIGHT_SLEEP_DURATION)

        while True:
            try:
                http_client, connector = await self.create_session_with_retry(user_agent)

                if proxy:
                    await self.check_proxy(http_client=http_client)

                if (datetime.now() - access_token_created_time >= token_live_time) or tg_web_data is None:
                    tg_web_data = await self.get_tg_web_data(proxy=proxy, bot_peer=self.main_bot_peer, ref=link,
                                                             short_name="app")
                    if tg_web_data is None:
                        continue

                    http_client.headers["Authorization"] = f"initData {tg_web_data}"
                    self.init_data = f"initData {tg_web_data}"
                    logger.info(f"{self.session_name} | Started login")
                    self.user_info = await self.login(http_client=http_client)
                    if not settings.RANDOM_PIXEL_MODE:
                        self.websocket_token = self.user_info["websocketToken"]
                        self.websocket = WebsocketManager(http_client=http_client, token=self.websocket_token)
                    logger.success(f"{self.session_name} | Successful login")

                    # Update access token creation time and token live time
                    access_token_created_time = datetime.now()
                    token_live_time = timedelta(seconds=randint(600, 800))

                await self.update_status(http_client=http_client)
                balance = await self.get_balance(http_client)
                logger.info(f"{self.session_name} | Balance: <e>{balance}</e>")
                await self.check_response(http_client=http_client)

                tasks = []

                if settings.AUTO_DRAW:
                    tasks.append(self.subscribe_and_paint(http_client=http_client))

                if settings.AUTO_UPGRADE:
                    tasks.append(self.upgrade(http_client=http_client))

                if settings.JOIN_SQUAD:
                    tasks.append(self.join_squad_if_not_in(user_agent=user_agent))

                if settings.CLAIM_REWARD:
                    tasks.append(self.claim(http_client=http_client))

                if settings.AUTO_TASK:
                    tasks.append(self.tasks(http_client=http_client))

                if settings.SUBSCRIBE_TOURNAMENT_TEMPLATE:
                    tasks.append(self.choose_and_subscribe_tournament_template(http_client=http_client))

                random.seed(os.urandom(8))
                random.shuffle(tasks)

                if tasks:
                    for task in tasks:
                        await task

            except InvalidSession as error:
                logger.error(f"{self.session_name} | Invalid Session: {error}")

            except InvalidProxyError as error:
                logger.error(f"{self.session_name} | {error}")

            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error: {error}")

            finally:
                await self.close_session(http_client, connector)
                if settings.NIGHT_MODE:
                    next_wakeup = sleep_manager.get_wake_up_time()
                    if next_wakeup:
                        logger.info(f"{self.session_name} | Night mode activated, Sleep until <y>"
                                    f"{next_wakeup.strftime('%d.%m.%Y %H:%M')}</y>")
                        sleep_seconds = (next_wakeup - datetime.now()).total_seconds()
                        await asyncio.sleep(delay=sleep_seconds)
                    else:
                        random.seed(os.urandom(8))
                        sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
                        logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                        await asyncio.sleep(delay=sleep_time)
                else:
                    random.seed(os.urandom(8))
                    sleep_time = random.randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])
                    logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                    await asyncio.sleep(delay=sleep_time)


async def run_tapper(tg_client: Client, user_agent: str, start_delay: int, proxy: str | None,
                     first_run: bool, pixel_chain=None):
    memory_cache = MemoryCache(max_size=128)

    tapper = Tapper(
        tg_client=tg_client,
        first_run=first_run,
        pixel_chain=pixel_chain,
        memory_cache=memory_cache,
        user_agent=user_agent
    )

    try:
        await tapper.run(user_agent=user_agent, proxy=proxy, start_delay=start_delay)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
