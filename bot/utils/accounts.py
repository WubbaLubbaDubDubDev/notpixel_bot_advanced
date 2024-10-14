import os
import random

from bot.core.agents import generate_random_user_agent
from bot.utils import logger
from bot.config import settings, telrgram_versions
from bot.utils.file_manager import load_from_json, save_to_json


class Accounts:
    def __init__(self):
        self.workdir = "sessions/"
        self.api_id = settings.API_ID
        self.api_hash = settings.API_HASH

    @staticmethod
    def get_available_accounts(sessions: list, proxy_chain=None):

        accounts_from_json = load_from_json('sessions/accounts.json')

        if not accounts_from_json:
            raise ValueError("Can't run script | Please, add account/s in sessions/accounts.json")

        available_accounts = []
        for session in sessions:
            is_session_added = False
            for saved_account in accounts_from_json:
                if saved_account['session_name'] == session:
                    available_accounts.append(saved_account)
                    is_session_added = True
                    break
            if not is_session_added:
                ans = None
                raw_proxy = None
                if proxy_chain:
                    raw_proxy = proxy_chain.get_next_proxy()
                else:
                    logger.warning(f'{session}.session does not exist in sessions/accounts.json')
                    ans = input(f"Add {session} to accounts.json? (y/N): ")
                if not proxy_chain and ('y' in ans.lower()):
                    raw_proxy = input("Input the proxy in the format type://user:pass@ip:port (press Enter to use "
                                      "without proxy): ")
                user_agent, android_version, android_device = generate_random_user_agent(browser_type='chrome')
                app_version = f"Telegram Android {random.choice(telrgram_versions.versions)}"
                new_account = {
                        "session_name": session,
                        "user_agent": user_agent,
                        "proxy": raw_proxy,
                        "android_device": android_device,
                        "android_version": android_version,
                        "app_version": app_version
                }
                save_to_json(f'sessions/accounts.json', dict_=new_account)
                available_accounts.append(new_account)
                if proxy_chain:
                    logger.success(f'Account {session} added successfully with proxy: {raw_proxy}')
        return available_accounts

    def pars_sessions(self):
        sessions = []
        for file in os.listdir(self.workdir):
            if file.endswith(".session"):
                sessions.append(file.replace(".session", ""))

        logger.info(f"Searched sessions: {len(sessions)}.")
        return sessions

    async def get_accounts(self, proxy_chain=None):
        sessions = self.pars_sessions()
        available_accounts = self.get_available_accounts(sessions, proxy_chain=proxy_chain)

        if not available_accounts:
            raise ValueError("Available accounts not found! Please add accounts in 'sessions' folder")
        else:
            logger.success(f"Available accounts: {len(available_accounts)}.")

        return available_accounts
