import json
import os


class ProxyChain:
    def __init__(self):
        self.proxies = []
        self.used_proxies = set()
        self.load_proxies_from_txt()
        self.load_proxies_from_json()

    def load_proxies_from_json(self):
        file_path = 'sessions/accounts.json'
        if not os.path.exists(file_path):
            with open(file_path, 'r') as file:
                data = json.load(file)
                for entry in data:
                    if 'proxy' in entry:
                        proxy = entry['proxy']
                        if proxy in self.proxies:
                            self.used_proxies.add(proxy)

    def load_proxies_from_txt(self):
        file_path = 'bot/config/proxies.txt'
        with open(file_path, 'r') as file:
            self.proxies.extend(line.strip() for line in file if line.strip())
        if len(self.proxies) == 0:
            raise ValueError("The proxy list is empty.")

    def get_next_proxy(self):
        for proxy in self.proxies:
            if proxy not in self.used_proxies:
                self.used_proxies.add(proxy)
                return proxy
        self.used_proxies.clear()
        return self.get_next_proxy()
