import asyncio
import json
import re
import os
import random
import base64
from time import time
from urllib.parse import unquote, quote
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
from ..utils.watchdog import Watchdog
from ..utils.firstrun import append_line_to_file
from bot.exceptions import InvalidSession
from .headers import headers, headers_squads
from random import randint, choices


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
        self.start_param = ''
        self.main_bot_peer = 'notpixel'
        self.squads_bot_peer = 'notgames_bot'
        self.watchdog = watchdog
        self.pixel_chain = pixel_chain

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
                    if self.watchdog:
                        await self.watchdog.track_error()
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
            if self.watchdog:
                await self.watchdog.track_error()
            raise error

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error during Authorization: {error}")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=3)

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
                if self.watchdog:
                    await self.watchdog.track_error()
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
                if self.watchdog:
                    await self.watchdog.track_error()

    async def login(self, http_client: aiohttp.ClientSession):
        try:
            response = await http_client.get("https://notpx.app/api/v1/users/me")
            response.raise_for_status()
            response_json = await response.json()
            return response_json

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when logging: {error}")
            logger.warning(f"{self.session_name} | Bot overloaded retrying logging in")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=randint(3, 7))
            await self.login(http_client)

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://ipinfo.io/ip', timeout=aiohttp.ClientTimeout(20))
            ip = (await response.text())
            logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"{self.session_name} | Proxy: {proxy} | Error: {error}")
            if self.watchdog:
                await self.watchdog.track_error()

    async def join_tg_channel(self, link: str):
        if not self.tg_client.is_connected:
            try:
                await self.tg_client.connect()
            except Exception as error:
                logger.error(f"{self.session_name} | Error while TG connecting: {error}")
                if self.watchdog:
                    await self.watchdog.track_error()

        try:
            parsed_link = link.split('/')[-1]
            logger.info(f"{self.session_name} | Joining tg channel {parsed_link}")
            await self.tg_client.join_chat(parsed_link)
            logger.success(f"{self.session_name} | Joined tg channel {parsed_link}")
            if self.tg_client.is_connected:
                await self.tg_client.disconnect()
        except Exception as error:
            logger.error(f"{self.session_name} | Error while join tg channel: {error}")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=3)

    async def get_balance(self, http_client: aiohttp.ClientSession):
        try:
            balance_req = await http_client.get('https://notpx.app/api/v1/mining/status')
            balance_req.raise_for_status()
            balance_json = await balance_req.json()
            return balance_json['userBalance']
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when processing balance: {error}")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=3)

    async def tasks(self, http_client: aiohttp.ClientSession):
        try:
            stats = await http_client.get('https://notpx.app/api/v1/mining/status')
            stats.raise_for_status()
            stats_json = await stats.json()
            done_task_list = stats_json['tasks'].keys()
            if randint(0, 5) == 3:
                league_statuses = {"bronze": [], "silver": ["leagueBonusSilver"],
                                   "gold": ["leagueBonusSilver", "leagueBonusGold"],
                                   "platinum": ["leagueBonusSilver", "leagueBonusGold", "leagueBonusPlatinum"]}
                possible_upgrades = league_statuses.get(stats_json["league"], "Unknown")
                if possible_upgrades == "Unknown":
                    logger.warning(
                        f"{self.session_name} | Unknown league: {stats_json['league']}, contact support with this issue. Provide this log to make league known.")
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
                        repaints_total = stats_json['repaintsTotal']
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
            if self.watchdog:
                await self.watchdog.track_error()

    async def in_squad(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Checking if you're in squad")
            stats_req = await http_client.get(f'https://notpx.app/api/v1/mining/status')
            stats_req.raise_for_status()
            stats_json = await stats_req.json()
            league = stats_json["league"]
            squads_req = await http_client.get(f'https://notpx.app/api/v1/ratings/squads?league={league}')
            squads_req.raise_for_status()
            squads_json = await squads_req.json()
            squad_id = squads_json.get("mySquad", {"id": None}).get("id", None)
            return True if squad_id else False
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when claiming reward: {error}")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=3)

    async def paint(self, http_client: aiohttp.ClientSession):
        try:
            stats = await http_client.get('https://notpx.app/api/v1/mining/status')
            stats.raise_for_status()
            stats_json = await stats.json()
            charges = stats_json['charges']
            colors = ("#e46e6e", "#FFD635", "#7EED56", "#00CCC0", "#51E9F4", "#94B3FF", "#E4ABFF",
                      "#FF99AA", "#FFB470", "#FFFFFF", "#BE0039", "#FF9600", "#00CC78", "#009EAA",
                      "#3690EA", "#6A5CFF", "#B44AC0", "#FF3881", "#9C6926", "#898D90", "#6D001A",
                      "#bf4300", "#00A368", "#00756F", "#2450A4", "#493AC1", "#811E9F", "#a00357",
                      "#6D482F", "#000000")

            for _ in range(charges):
                random.seed(os.urandom(8))

                if self.pixel_chain:
                    x, y, color = self.pixel_chain.get_pixel()
                    pixel_id = get_pixel_id(x, y)
                else:
                    color = random.choice(colors)
                    pixel_id = random.randint(1, 1000000)
                    x, y = get_coordinates(pixel_id=pixel_id, width=1000)

                paint_request = await http_client.post('https://notpx.app/api/v1/repaint/start',
                                                       json={"pixelId": pixel_id, "newColor": color})
                paint_request.raise_for_status()
                logger.info(f"{self.session_name} | Painted on ({x}, {y}) with color {color}")
                await asyncio.sleep(delay=randint(5, 10))

        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when processing tasks: {error}")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=3)

    async def upgrade(self, http_client: aiohttp.ClientSession):
        while True:
            try:
                status_req = await http_client.get('https://notpx.app/api/v1/mining/status')
                status_req.raise_for_status()
                status = await status_req.json()
                boosts = status['boosts']
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
                                logger.warning(f"{self.session_name} | Not enough money to keep upgrading {name}.")
                                await asyncio.sleep(delay=randint(2, 5))
                    except Exception as error:
                        logger.error(f"{self.session_name} | Unknown error when upgrading {name}: {error}")
                        if self.watchdog:
                            await self.watchdog.track_error()
                        await asyncio.sleep(delay=3)
            except Exception as error:
                logger.error(f"{self.session_name} | Unknown error when upgrading: {error}")
                if self.watchdog:
                    await self.watchdog.track_error()
                await asyncio.sleep(delay=3)
            return

    async def claim(self, http_client: aiohttp.ClientSession):
        try:
            logger.info(f"{self.session_name} | Claiming mine")
            response = await http_client.get(f'https://notpx.app/api/v1/mining/status')
            response.raise_for_status()
            response_json = await response.json()
            await asyncio.sleep(delay=5)
            for _ in range(2):
                try:
                    await asyncio.sleep(delay=60)
                    response = await http_client.get(f'https://notpx.app/api/v1/mining/claim')
                    response.raise_for_status()
                    response_json = await response.json()
                except Exception as error:
                    logger.info(f"{self.session_name} | First claiming not always successful, retrying..")
                    if self.watchdog:
                        await self.watchdog.track_error()
                    await asyncio.sleep(delay=5)
                else:
                    break

            return response_json['claimed']
        except Exception as error:
            logger.error(f"{self.session_name} | Unknown error when claiming reward: {error}")
            if self.watchdog:
                await self.watchdog.track_error()
            await asyncio.sleep(delay=3)

    async def run(self, user_agent: str, proxy: str | None) -> None:
        access_token_created_time = 0
        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None
        headers["User-Agent"] = user_agent

        async with aiohttp.ClientSession(headers=headers, connector=proxy_conn, trust_env=True) as http_client:
            if proxy:
                await self.check_proxy(http_client=http_client, proxy=proxy)

            ref = settings.REF_ID
            link = get_link(ref)

            delay = randint(settings.START_DELAY[0], settings.START_DELAY[1])
            logger.info(f"{self.session_name} | Start delay {delay} seconds")
            await asyncio.sleep(delay=delay)

            token_live_time = randint(3500, 3600)
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
                        token_live_time = randint(3500, 3600)
                        sleep_time = randint(settings.SLEEP_TIME[0], settings.SLEEP_TIME[1])

                        await asyncio.sleep(delay=randint(1, 3))

                        balance = await self.get_balance(http_client)
                        logger.info(f"{self.session_name} | Balance: <e>{balance}</e>")

                        if settings.AUTO_DRAW:
                            await self.paint(http_client=http_client)

                        if settings.AUTO_UPGRADE:
                            reward_status = await self.upgrade(http_client=http_client)

                        if randint(1, 8) == 5:
                            if not await self.in_squad(http_client=http_client):
                                tg_web_data = await self.get_tg_web_data(proxy=proxy, bot_peer=self.squads_bot_peer,
                                                                         ref="cmVmPTQ2NDg2OTI0Ng==",
                                                                         short_name="squads")
                                await self.join_squad(tg_web_data, proxy_conn, user_agent)
                            else:
                                logger.success(f"{self.session_name} | You're already in squad")

                        if settings.CLAIM_REWARD:
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


async def run_tapper(tg_client: Client, user_agent: str, proxy: str | None, first_run: bool, pixel_chain=None):
    watchdog = Watchdog(max_errors=5, time_window=timedelta(minutes=2), sleep_duration=timedelta(hours=1),
                        client_name=tg_client.name)
    try:
        await (Tapper(tg_client=tg_client, first_run=first_run, watchdog=watchdog, pixel_chain=pixel_chain)
               .run(user_agent=user_agent, proxy=proxy))
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
