import random

from better_proxy import Proxy
from pyrogram import Client
from bot.config import settings, telegram_versions
from bot.core.agents import generate_random_user_agent
from bot.utils import logger
from bot.utils.file_manager import save_to_json


async def register_sessions(proxy_chain = None) -> None:
    API_ID = settings.API_ID
    API_HASH = settings.API_HASH

    if not API_ID or not API_HASH:
        raise ValueError("API_ID and API_HASH not found in the .env file.")

    session_name = input('\nEnter the session name (press Enter to exit): ')

    if not session_name:
        return None

    user_agent, android_version, android_device, app_version_ = generate_random_user_agent()
    app_version = f"Telegram Android {app_version_}"

    if proxy_chain:
        raw_proxy = proxy_chain.get_next_proxy()
    else:
        raw_proxy = input("Input the proxy in the format type://user:pass@ip:port (press Enter to use without proxy): ")

    session = await get_tg_client(session_name=session_name, android_version=android_version,
                                  android_device=android_device, app_version=app_version, proxy=raw_proxy)
    async with session:
        user_data = await session.get_me()

    save_to_json(f'sessions/accounts.json',
                 dict_={
                    "session_name": session_name,
                    "user_agent": user_agent,
                    "proxy": raw_proxy if raw_proxy else "",
                    "android_device": android_device,
                    "android_version": android_version,
                    "app_version": app_version
                 })
    logger.success(f'Session added successfully @{user_data.username} | {user_data.first_name} {user_data.last_name}')


async def get_tg_client(session_name: str,
                        proxy: str | None, android_version: str = "", android_device: str = "",
                        app_version: str = "") -> Client:
    if not session_name:
        raise FileNotFoundError(f"Not found session {session_name}")

    if not settings.API_ID or not settings.API_HASH:
        raise ValueError("API_ID and API_HASH not found in the .env file.")

    # Create a Proxy object from the proxy string
    if proxy:
        proxy = Proxy.from_str(proxy=proxy)
    else:
        proxy = None

    # Form a dictionary with the necessary parameters
    proxy_dict = {
        "scheme": proxy.protocol,
        "username": proxy.login,
        "password": proxy.password,
        "hostname": proxy.host,
        "port": proxy.port
    } if proxy else None

    # Client parameters
    client_params = {
        "name": session_name,
        "api_id": settings.API_ID,
        "api_hash": settings.API_HASH,
        "workdir": "sessions/",
        "sleep_threshold": 123
    }

    # Додаємо опціональні параметри, якщо вони задані
    if app_version:
        client_params["app_version"] = app_version
    if android_device:
        client_params["device_model"] = android_device
    if android_version:
        client_params["system_version"] = f"Android {android_version}"
    if proxy_dict:
        client_params["proxy"] = proxy_dict

    # Створення клієнта з динамічними параметрами
    tg_client = Client(**client_params)

    return tg_client
