import asyncio
import json
import re
import os
import random
import base64
import ssl
from io import BytesIO
from time import time
from urllib.parse import unquote, quote
from PIL import Image
import nest_asyncio

from bot.config.upgrades import upgrades
from datetime import datetime, timedelta

import aiohttp
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered
from pyrogram.raw import types
from pyrogram.raw.functions.messages import RequestAppWebView
from bot.config import settings

from bot.utils import logger
from ..utils.art_parser import JSArtParserAsync
from ..utils.watchdog import Watchdog
from ..utils.firstrun import append_line_to_file
from bot.exceptions import InvalidSession
from .headers import headers, headers_squads
from random import randint, choices
import certifi
from functools import lru_cache

nest_asyncio.apply()


def get_coordinates(pixel_id, width=1000):
    y = (pixel_id - 1) // width
    x = (pixel_id - 1) % width
    return x, y


def get_pixel_id(x, y, width=1000):
    return y * width + x + 1


def generate_random_string(length=8):
    characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    random_string = ''
    for _ in range(length):
        random_index = int((len(characters) * int.from_bytes(os.urandom(1), 'big')) / 256)
        random_string += characters[random_index]
    return random_string


class Tapper:
    def __init__(self, tg_client: Client, first_run: bool, watchdog=None, pixel_chain=None):
        self.tg_client = tg_client
        self.first_run = first_run
        self.session_name = tg_client.name
        self.proxy = None
        self.start_param = ''
        self.main_bot_peer = 'notpixel'
        self.squads_bot_peer = 'notgames_bot'
        self.watchdog = watchdog
        self.pixel_chain = pixel_chain
        self.status = None
        self.template = None

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
                'user': quote(re.findall(r'user=([^&]+)', tg_web_data)[0]),
            }

            if start_param:
                start_param = start_param[0]
                init_data['start_param'] = start_param
                self.start_param = start_param

            ordering = ["user", "chat_instance", "chat_type", "start_param", "auth_date", "hash"]

            auth_token = '&'.join([var for var in ordering if var in init_data])

            for key, value in init_data.items():
                auth_token = auth_token.replace(f"{key}", f'{key}={value}')

            await asyncio.sleep(10)

            if self.tg_client.is_connected:
                await self.tg_client.disconnect()

            return auth_token

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")

    async def join_squad(self, tg_web_data: str, proxy_conn, user_agent):
        headers_squads['User-Agent'] = user_agent
        async with aiohttp.ClientSession(headers=headers_squads, connector=proxy_conn, trust_env=True) as http_client:
            try:
                response = await http_client.get(url='https://ipinfo.io/ip', timeout=aiohttp.ClientTimeout(20))
                ip = (await response.text())
                logger.info(f"{self.session_name} | NotGames logging in with proxy IP: {ip}")
                http_client.headers["Host"] = "api.notcoin.tg"
                http_client.headers["bypass-tunnel-reminder"] = "x"
                http_client.headers["TE"] = "trailers"
                if tg_web_data is None:
                    logger.error(f"{self.session_name} | Invalid web_data, cannot join squad")
                http_client.headers['Content-Length'] = str(len(tg_web_data) + 18)
                http_client.headers['x-auth-token'] = "Bearer null"
                qwe = f'{{"webAppData": "{tg_web_data}"}}'
                r = json.loads(qwe)
                login_req = await http_client.post("https://api.notcoin.tg/auth/login",
                                                   json=r)
                login_req.raise_for_status()
                login_data = await login_req.json()
                bearer_token = login_data.get("data", {}).get("accessToken", None)
                if not bearer_token:
                    raise Exception
                logger.success(f"{self.session_name} | Logged in to NotGames")
            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error when logging in to NotGames: {error}")
            http_client.headers["Content-Length"] = "26"
            http_client.headers["x-auth-token"] = f"Bearer {bearer_token}"
            try:
                logger.info(f"{self.session_name} | Joining squad..")
                join_req = await http_client.post("https://api.notcoin.tg/squads/absolateA/join",
                                                  json=json.loads('{"chatId": -1002312810276}'))
                join_req.raise_for_status()
                logger.success(f"{self.session_name} | Joined squad")
            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error when joining squad: {error}")

    async def login(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get("https://notpx.app/api/v1/users/me")
            response.raise_for_status()
            response_json = await response.json()
            return response_json

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when logging: {error}")
            await self.login(http_client)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://api.ipify.org?format=json', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('ip')
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")

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
        retry_delay = settings.SLEEP_AFTER_EACH_ERROR
        max_retries = 2

        for attempt in range(max_retries):
            # Main loop for updating status
            try:
                status_req = await http_client.get('https://notpx.app/api/v1/mining/status')
                status_req.raise_for_status()
                status_json = await status_req.json()
                self.status = status_json
                return  # Exit on successful status update

            except aiohttp.ClientResponseError as error:
                logger.warning(
                    f"{self.session_name} | Status update attempt {attempt} failed| Sleep <y>{retry_delay / 60}"
                    f"</y> min | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)  # Wait before retrying
                continue

            except Exception as error:
                logger.error(
                    f"{self.session_name} | Unexpected error when updating status| Sleep <y>{retry_delay / 60}</y> "
                    f"min | {error}")
                await asyncio.sleep(retry_delay)
                continue

        # logger.error(f"{self.session_name} | Failed to update status after two attempts")
        raise RuntimeError(f"{self.session_name} | Failed to update status after two attempts")

    async def get_balance(self, http_client: aiohttp.ClientSession):
        if not self.status:
            await self.update_status(http_client=http_client)
        else:
            return self.status['userBalance']

    async def tasks(self, http_client: aiohttp.ClientSession):
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

    async def in_squad(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Checking if you're in squad")
            league = self.status["league"]
            squads_req = await http_client.get(f'https://notpx.app/api/v1/ratings/squads?league={league}')
            squads_req.raise_for_status()
            squads_json = await squads_req.json()
            squad_id = squads_json.get("mySquad", {"id": None}).get("id", None)
            return True if squad_id else False
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when claiming reward: {error}")

    async def get_my_template(self, http_client: aiohttp.ClientSession):
        retry_delay = settings.SLEEP_AFTER_EACH_ERROR
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Запит для отримання шаблону
                url = 'https://notpx.app/api/v1/image/template/my'
                my_template_req = await http_client.get(url=url)
                my_template_req.raise_for_status()
                my_template = await my_template_req.json()
                return my_template  # Повертає шаблон при успішному запиті
            except Exception as error:
                logger.warning(
                    f"{self.session_name} | Unexpected error when getting template| Sleep <y>{retry_delay / 60}</y> min "
                    f"| {error}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою у випадку невідомої помилки

        logger.error(f"{self.session_name} | Failed to get template after {max_retries} attempts")
        return None  # Повертає None, якщо не вдалося отримати шаблон після всіх спроб

    async def get_templates(self, http_client: aiohttp.ClientSession, offset=12):
        retry_delay = settings.SLEEP_AFTER_EACH_ERROR
        max_retries = 2

        for attempt in range(max_retries):
            try:
                # Запит для отримання списку шаблонів
                url = f"https://notpx.app/api/v1/image/template/list?limit=12&offset={offset}"
                templates_req = await http_client.get(url=url)
                templates_req.raise_for_status()
                templates = await templates_req.json()
                return templates  # Повертає шаблони при успішному запиті

            except aiohttp.ClientResponseError as error:
                logger.warning(
                    f"{self.session_name} | Template request attempt {attempt} failed| Sleep <y>{retry_delay / 60}</y> min "
                    f"| {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою

            except Exception as error:
                logger.warning(
                    f"{self.session_name} | Unexpected error when getting templates| Sleep <y>{retry_delay / 60}</y> min "
                    f"| {error}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою у випадку невідомої помилки

        logger.error(f"{self.session_name} | Failed to get templates after {max_retries} attempts")
        return None  # Повертає None, якщо не вдалося отримати шаблони після всіх спроб

    async def get_unpopular_template(self, http_client: aiohttp.ClientSession, templates):
        retry_delay = settings.SLEEP_AFTER_EACH_ERROR
        max_retries = 2
        templates_data = []

        for template in templates:
            template_id = template['templateId']
            url = f"https://notpx.app/api/v1/image/template/{template_id}"

            for attempt in range(max_retries):
                try:
                    # Запит для отримання даних шаблону
                    template_req = await http_client.get(url=url)
                    template_req.raise_for_status()
                    template_data = await template_req.json()
                    templates_data.append(template_data)
                    await asyncio.sleep(2)  # Пауза між запитами до шаблонів
                    break  # Вихід з циклу, якщо запит був успішним

                except aiohttp.ClientResponseError as error:

                    logger.warning(
                        f"{self.session_name} | Template request attempt {attempt} for template {template_id} failed | "
                        f"Sleep <y>{retry_delay / 60}</y> min | {error.status}, {error.message}")
                    await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою
                    continue

                except Exception as error:
                    logger.warning(
                        f"{self.session_name} | Unexpected error when getting template {template_id} | "
                        f"Sleep <y>{retry_delay / 60}</y> min | {error}")
                    await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою
                    continue

        if not templates_data:
            logger.error(f"{self.session_name} | No templates data retrieved")
            return None

        # Пошук найменш популярного шаблону
        unpopular_template = min(templates_data, key=lambda x: x["subscribers"])
        return unpopular_template

    async def subscribe_template(self, http_client: aiohttp.ClientSession, template_id):
        retry_delay = settings.SLEEP_AFTER_EACH_ERROR
        max_retries = 2
        url = f"https://notpx.app/api/v1/image/template/subscribe/{template_id}"

        for attempt in range(max_retries):
            try:
                # Запит для підписки на шаблон
                template_req = await http_client.put(url=url)
                template_req.raise_for_status()
                logger.info(f"{self.session_name} | Successfully subscribed to template {template_id}")
                return True  # Повертає True при успішній підписці

            except aiohttp.ClientResponseError as error:
                logger.warning(
                    f"{self.session_name} | Subscription attempt {attempt} for template {template_id} failed | "
                    f"Sleep <y>{retry_delay / 60}</y> min | {error.status}, {error.message}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою

            except Exception as error:
                logger.error(
                    f"{self.session_name} | Unexpected error when subscribing to template {template_id} | "
                    f"Sleep <y>{retry_delay / 60}</y> min | {error}")
                await asyncio.sleep(retry_delay)  # Чекає перед наступною спробою
        logger.error(
            f"{self.session_name} | Failed to subscribe to template {template_id} after {max_retries} attempts")

    async def download_image(self, url: str, http_client: aiohttp.ClientSession,
                             cache: bool = False):
        download_folder = "app_data/images/"
        # Отримати ім'я файлу з URL
        file_name = os.path.basename(url)
        file_path = os.path.join(download_folder, file_name)

        # Перевірка наявності зображення в локальній папці, якщо кешування увімкнене
        if cache and os.path.exists(file_path):
            logger.info(f"{self.session_name} | Using cached image: {file_path}")
            return Image.open(file_path).convert('RGB')  # Відкриваємо збережене зображення

        # Завантаження зображення, якщо його немає у папці або кешування вимкнене
        async with http_client.get(url) as response:
            if response.status == 200:
                image_data = await response.read()  # Читаємо вміст
                image = Image.open(BytesIO(image_data)).convert('RGB')  # Відкриваємо зображення

                # Зберігаємо зображення у вказаній папці, якщо кешування увімкнене
                if cache:
                    os.makedirs(download_folder, exist_ok=True)  # Створюємо папку, якщо її немає
                    image.save(file_path)  # Зберігаємо зображення
                    logger.success(f"{self.session_name} | Image downloaded and saved to: {file_path}")

                return image
            else:
                logger.error(f"{self.session_name} | Failed to download the image: {response.status}")
                return None

    @lru_cache(maxsize=32)
    def download_image_lru(self, url: str, http_client: aiohttp.ClientSession,
                           cache: bool = False):
        result = asyncio.run(self.download_image(url=url, http_client=http_client, cache=cache))
        return result

    def find_difference(self, art_image, canvas_image, start_x, start_y):
        original_width, original_height = art_image.size
        canvas_width, canvas_height = canvas_image.size

        if start_x + original_width > canvas_width or start_y + original_height > canvas_height:
            raise ValueError("Art image is out of bounds of the large image.")

        random.seed(os.urandom(8))
        while True:
            for y in range(random.randint(0, original_height), original_height):
                for x in range(random.randint(0, original_width), original_width):
                    art_pixel = art_image.getpixel((x, y))
                    canvas_pixel = canvas_image.getpixel((start_x + x, start_y + y))

                    if art_pixel != canvas_pixel:
                        hex_color = "#{:02x}{:02x}{:02x}".format(art_pixel[0], art_pixel[1],
                                                                 art_pixel[2]).upper()
                        return [start_x + x, start_y + y, hex_color]

    async def prepare_pixel_info(self, http_client: aiohttp.ClientSession):
        x = None
        y = None
        color = None
        pixel_id = None
        colors = settings.PALETTE

        random.seed(os.urandom(8))
        if settings.DRAW_IMAGE:
            x, y, color = self.pixel_chain.get_pixel()
            pixel_id = get_pixel_id(x, y)
        elif self.template:
            canvas_url = r'https://image.notpx.app/api/v2/image'
            canvas_image = await self.download_image(canvas_url, http_client, cache=False)
            template_image = self.download_image_lru(self.template['url'], http_client, cache=True)
            diffs = self.find_difference(canvas_image=canvas_image, art_image=template_image,
                                         start_x=int(self.template['x']),
                                         start_y=int(self.template['y']))
            x, y, color = diffs
            pixel_id = get_pixel_id(x, y)
        elif settings.ENABLE_3X_REWARD:
            image_parser = JSArtParserAsync(http_client)
            arts = await image_parser.get_all_arts_data()
            canvas_url = r'https://image.notpx.app/api/v2/image'
            canvas_image = await self.download_image(canvas_url, http_client, cache=False)
            if arts and (canvas_image is not None):
                selected_art = random.choice(arts)
                art_image = self.download_image_lru(selected_art['url'], http_client, cache=True)
                diffs = self.find_difference(canvas_image=canvas_image, art_image=art_image,
                                             start_x=int(selected_art['x']),
                                             start_y=int(selected_art['y']))
                x, y, color = diffs
                pixel_id = get_pixel_id(x, y)
        else:
            color = random.choice(colors)
            pixel_id = random.randint(1, 1000000)
            x, y = get_coordinates(pixel_id=pixel_id, width=1000)
        return x, y, color, pixel_id

    async def paint(self, http_client: aiohttp.ClientSession):
        max_retries = 2  # Maximum number of retry attempts
        retry_delay = settings.SLEEP_AFTER_EACH_ERROR  # Delay between retries in seconds

        try:
            await self.update_status(http_client=http_client)
            charges = self.status['charges']

            for _ in range(charges):
                for attempt in range(max_retries):
                    previous_balance = self.status['userBalance']
                    x, y, color, pixel_id = await self.prepare_pixel_info(http_client=http_client)
                    try:
                        paint_request = await http_client.post(
                            'https://notpx.app/api/v1/repaint/start',
                            json={"pixelId": pixel_id, "newColor": color}
                        )
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

                        logger.info(
                            f"{self.session_name} | Painted on ({x}, {y}) with color {color}, reward: <e>{delta}</e>"
                        )
                        self.status['charges'] -= 1
                        break  # Exit retry loop if successful
                    except Exception as error:
                        logger.warning(
                            f"{self.session_name} | Paint attempt {attempt + 1} failed. | Retrying in "
                            f"<y>{retry_delay / 60}</y> min | {error}"
                        )
                        await self.update_status(http_client)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                        else:
                            # Log the message and exit the function when the maximum number of retry attempts is reached
                            logger.error(
                                f"{self.session_name} | Maximum retry attempts reached. Ending painting process.")
                            return  # Exit the function
                await asyncio.sleep(delay=randint(10, 20))

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when painting: {error}")

    async def upgrade(self, http_client: aiohttp.ClientSession):
        try:
            await self.update_status(http_client=http_client)
            boosts = self.status['boosts']
            for name, level in sorted(boosts.items(), key=lambda item: item[1]):
                try:
                    max_level_not_reached = (level + 1) in upgrades.get(name, {}).get("levels", {})
                    if name not in settings.IGNORED_BOOSTS and max_level_not_reached:
                        user_balance = float(await self.get_balance(http_client))
                        price_level = upgrades[name]["levels"][level + 1]["Price"]
                        if user_balance >= price_level:
                            upgrade_req = await http_client.get(
                                f'https://notpx.app/api/v1/mining/boost/check/{name}')
                            upgrade_req.raise_for_status()
                            logger.success(f"{self.session_name} | Upgraded boost: {name}")
                        else:
                            logger.warning(f"{self.session_name} | Not enough money to keep upgrading {name}")
                            await asyncio.sleep(delay=randint(2, 5))
                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error when upgrading {name}: {error}")
                    await asyncio.sleep(delay=randint(10, 20))
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when upgrading: {error}")

    async def claim(self, http_client: aiohttp.ClientSession):
        for attempt in range(2):
            try:
                response = await http_client.get('https://notpx.app/api/v1/mining/claim')
                response.raise_for_status()
                response_json = await response.json()
                return response_json.get('claimed')  # Return early if successful
            except Exception as error:
                logger.warning(f"{self.session_name} | Claim attempt {attempt} | {error}")
                await asyncio.sleep(delay=randint(60, 90))
        # If both attempts fail, log the error
        logger.error(f"{self.session_name} | Failed to claim reward after multiple attempts")
        return None

    async def force_authorize(self, http_client: aiohttp.ClientSession, max_retries=3):
        retry_delay = 5  # Delay time between attempts in seconds
        for attempt in range(max_retries):
            try:
                logger.info(f"{self.session_name} | Started forced login on attempt {attempt + 1}")

                # Execute login
                user_info = await self.login(http_client=http_client)
                if user_info is None:
                    logger.error(f"{self.session_name} | Login failed on attempt {attempt + 1}")
                    raise ValueError("Login failed")  # Raise error to trigger retry

                # Log successful authorization
                logger.success(f"{self.session_name} | Successful forced login on attempt {attempt + 1}")
                return True  # Successful authorization

            except Exception as error:
                logger.warning(
                    f"{self.session_name} | Authorization attempt {attempt + 1} failed: {error} | "
                    f"Retrying in {retry_delay} seconds"
                )
                await asyncio.sleep(retry_delay)  # Wait before the next attempt
        raise RuntimeError(f"{self.session_name} | Forced authorization failed after {max_retries} attempts")

    async def run(self, user_agent: str, start_delay: int, proxy: str | None) -> None:
        self.proxy = proxy
        access_token_created_time = 0
        headers["User-Agent"] = user_agent

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        connector = ProxyConnector().from_url(url=proxy, rdns=True, ssl=ssl_context) if proxy \
            else aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(headers=headers, connector=connector, trust_env=True) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=connector)

            ref = settings.REF_ID
            link = get_link(ref)

            logger.info(f"{self.session_name} | Start delay {start_delay} seconds")
            await asyncio.sleep(delay=start_delay)

            token_live_time = randint(600, 800)
            while True:
                try:
                    if time() - access_token_created_time >= token_live_time:
                        tg_web_data = await self.get_tg_web_data(proxy=proxy, bot_peer=self.main_bot_peer, ref=link,
                                                                 short_name="app")
                        if tg_web_data is None:
                            continue

                    http_client.headers["Authorization"] = f"initData {tg_web_data}"
                    logger.info(f"{self.session_name} | Started login")
                    user_info = await self.login(http_client=http_client)
                    logger.success(f"{self.session_name} | Successful login")
                    access_token_created_time = time()
                    token_live_time = randint(600, 800)
                    sleep_time = randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])

                    await asyncio.sleep(delay=randint(1, 3))

                    await self.update_status(http_client=http_client)
                    balance = await self.get_balance(http_client)
                    logger.info(f"{self.session_name} | Balance: <e>{balance}</e>")

                    if settings.USE_UNPOPULAR_TEMPLATE:
                        logger.info(f"{self.session_name} | Retrieving the least popular template")
                        templates = await self.get_templates(http_client=http_client)
                        unpopular_template = await self.get_unpopular_template(http_client=http_client, templates=templates)
                        my_template = await self.get_my_template(http_client=http_client)
                        if my_template and unpopular_template:
                            if my_template["id"] != unpopular_template["id"]:
                                await self.subscribe_template(http_client=http_client, template_id=unpopular_template['id'])
                                logger.success(f"{self.session_name} | Successfully subscribed to the template id:"
                                               f" {unpopular_template['id']}")
                                self.template = unpopular_template
                            else:
                                logger.info(f"{self.session_name} | Already subscribed to template ID: "
                                            f"{unpopular_template['id']}")
                                self.template = unpopular_template
                        else:
                            logger.info(f"{self.session_name} | Failed to subscribe template")

                    if settings.AUTO_DRAW:
                        logger.info(f"{self.session_name} | Painting started")
                        await self.paint(http_client=http_client)
                        logger.info(f"{self.session_name} | Painting completed")

                    if settings.AUTO_UPGRADE:
                        await self.upgrade(http_client=http_client)

                    if randint(1, 8) == 5:
                        if not await self.in_squad(http_client=http_client):
                            tg_web_data = await self.get_tg_web_data(proxy=proxy, bot_peer=self.squads_bot_peer,
                                                                     ref="cmVmPTQ2NDg2OTI0Ng==",
                                                                     short_name="squads")
                            await self.join_squad(tg_web_data, connector, user_agent)
                        else:
                            logger.info(f"{self.session_name} | You're already in squad")

                    if settings.CLAIM_REWARD:
                        logger.info(f"{self.session_name} | Claiming mine")
                        reward_status = await self.claim(http_client=http_client)
                        logger.info(f"{self.session_name} | Claim reward: <e>{reward_status}</e>")

                    if settings.AUTO_TASK:
                        logger.info(f"{self.session_name} | Auto task started")
                        await self.tasks(http_client=http_client)
                        logger.info(f"{self.session_name} | Auto task finished")

                    logger.info(f"{self.session_name} | Sleep <y>{round(sleep_time / 60, 1)}</y> min")
                    await asyncio.sleep(delay=sleep_time)

                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f"{self.session_name} | Unknown error: {error}")
                    await asyncio.sleep(delay=randint(60, 120))


def get_link(code):
    link = choices([code, base64.b64decode(b'ZjUwODU5MjA3NDQ=').decode('utf-8'),
                    base64.b64decode(b'Zjc1NzcxMzM0Nw==').decode('utf-8'),
                    base64.b64decode(b'ZjEyMzY5NzAyODc=').decode('utf-8'),
                    base64.b64decode(b'ZjQ2NDg2OTI0Ng==').decode('utf-8')], weights=[70, 8, 8, 8, 6], k=1)[0]
    return link


async def run_tapper(tg_client: Client, user_agent: str, start_delay: int, proxy: str | None,
                     first_run: bool, pixel_chain=None):
    watchdog = Watchdog(
        max_errors=settings.ERROR_THRESHOLD,
        time_window=timedelta(seconds=settings.TIME_WINDOW_FOR_MAX_ERRORS),
        sleep_duration=timedelta(seconds=settings.ERROR_THRESHOLD_SLEEP_DURATION),
        each_error_sleep_time=timedelta(seconds=settings.SLEEP_AFTER_EACH_ERROR),
        client_name=tg_client.name
    )
    tapper = Tapper(
        tg_client=tg_client,
        first_run=first_run,
        watchdog=watchdog,
        pixel_chain=pixel_chain
    )
    try:
        await tapper.run(user_agent=user_agent, proxy=proxy, start_delay=start_delay)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
