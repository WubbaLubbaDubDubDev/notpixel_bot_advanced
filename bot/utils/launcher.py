import asyncio
import argparse
from random import randint
from typing import Any
from PIL import Image

from bot.utils import logger
from bot.core.tapper import run_tapper
from bot.core.registrator import register_sessions, get_tg_client
from bot.utils.accounts import Accounts
from bot.utils.firstrun import load_session_names
from bot.utils.pixel_chain import PixelChain
from bot.utils.proxy_chain import ProxyChain
from bot.config import settings

art_work = """

888b    888          888    8888888b.  d8b                   888 
8888b   888          888    888   Y88b Y8P                   888 
88888b  888          888    888    888                       888 
888Y88b 888  .d88b.  888888 888   d88P 888 888  888  .d88b.  888 
888 Y88b888 d88""88b 888    8888888P"  888 `Y8bd8P' d8P  Y8b 888 
888  Y88888 888  888 888    888        888   X88K   88888888 888 
888   Y8888 Y88..88P Y88b.  888        888 .d8""8b. Y8b.     888 
888    Y888  "Y88P"   "Y888 888        888 888  888  "Y8888  888 
                                                                 
                                                                 by Surinity                                    
"""

version = "            Advanced edition by WubbaLubbaDubDubDev      "

start_text = """                                             
Select an action:

    1. Run bot
    2. Create session
    
"""

proxy_chain = None
if settings.AUTO_BIND_PROXIES_FROM_FILE:
    proxy_chain = ProxyChain()


async def process() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--action", type=int, help="Action to perform")
    action = parser.parse_args().action

    if not action:
        print('\033[1m' + '\033[92m' + art_work + '\033[0m')
        print('\033[1m' + '\033[93m' + version + '\033[0m')

        #if settings.AUTO_TASK:
            #logger.warning("Auto Task is enabled, it is dangerous functional")

        print(start_text)

        while True:
            action = input("> ")

            if not action.isdigit():
                logger.warning("Action must be number")
            elif action not in ["1", "2"]:
                logger.warning("Action must be 1 or 2")
            else:
                action = int(action)
                break

    used_session_names = load_session_names()

    if action == 2:
        await register_sessions(proxy_chain=proxy_chain)
    elif action == 1:
        accounts = await Accounts().get_accounts(proxy_chain=proxy_chain)
        await run_tasks(accounts=accounts, used_session_names=used_session_names)


async def run_tasks(accounts: [Any, Any, list], used_session_names: [str]):
    tasks = []
    chain = None
    if settings.DRAW_IMAGE:
        image = Image.open(settings.IMAGE_PATH)
        coordinates = settings.DRAWING_START_COORDINATES
        chain = PixelChain(image, coordinates[0], coordinates[1], 1000, 1000)
    delay_between_account = 0
    for account in accounts:
        session_name = account.get("session_name")
        user_agent = account.get('user_agent')
        raw_proxy = account.get('proxy')
        android_device = account.get('android_device')
        android_version = account.get('android_version')
        app_version = account.get('app_version')
        first_run = session_name not in used_session_names
        tg_client = await get_tg_client(session_name=session_name, proxy=raw_proxy,
                                        android_device=android_device, android_version=android_version,
                                        app_version=app_version)
        tasks.append(asyncio.create_task(run_tapper(tg_client=tg_client, user_agent=user_agent, proxy=raw_proxy,
                                                    first_run=first_run, pixel_chain=chain,
                                                    start_delay=delay_between_account)))
        delay_between_account = randint(settings.START_DELAY[0], settings.START_DELAY[1])
        await asyncio.sleep(randint(5, 20))

    await asyncio.gather(*tasks)
