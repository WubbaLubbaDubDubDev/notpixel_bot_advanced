import json

class ProxyChain:
    def __init__(self):
        self.proxies = []
        self.used_proxies = set()
        self.load_proxies_from_txt()
        self.load_proxies_from_json()

    def load_proxies_from_json(self):
        """Load proxies from a JSON file."""
        file_path = 'sessions/accounts.json'
        with open(file_path, 'r') as file:
            data = json.load(file)
            # Extract proxy strings from each entry
            for entry in data:
                if 'proxy' in entry:
                    proxy = entry['proxy']
                    if proxy in self.proxies:  # Перевірка, чи проксі є в загальному списку
                        self.used_proxies.add(proxy)  # Додаємо у список використаних

    def load_proxies_from_txt(self):
        """Load proxies from a text file."""
        file_path = 'bot/config/proxies.txt'
        with open(file_path, 'r') as file:
            self.proxies.extend(line.strip() for line in file if line.strip())
        if len(self.proxies) == 0:
            raise ValueError("The proxy list is empty.")

    def get_next_proxy(self):
        """Get the next unused proxy, or restart if all are used."""
        for proxy in self.proxies:
            if proxy not in self.used_proxies:
                self.used_proxies.add(proxy)
                return proxy
        # If all proxies are used, reset and start again
        self.used_proxies.clear()
        return self.get_next_proxy()
