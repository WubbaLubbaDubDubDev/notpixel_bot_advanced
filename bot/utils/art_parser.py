import aiohttp
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class JSArtParserAsync:
    def __init__(self, http_client):
        self.url = "https://app.notpx.app/"
        self.js_filename = 'index-BkVcn5IH.js'
        self.session = http_client
        self.js_content = None

    async def download_html(self):
        try:
            async with self.session.get(self.url) as response:
                response.raise_for_status()
                return await response.text()
        except aiohttp.ClientError as e:
            print(f"Не вдалося завантажити HTML: {e}")
            return None

    def find_js_file(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        scripts = soup.find_all('script', src=True)
        for script in scripts:
            if self.js_filename in script['src']:
                return script['src']
        return None

    async def download_js(self, js_url):
        try:
            async with self.session.get(js_url) as response:
                response.raise_for_status()
                self.js_content = await response.text()
        except aiohttp.ClientError as e:
            self.js_content = None

    def parse_image_constants(self, constant_name):
        pattern = rf'{constant_name}\s*=\s*"([^"]+)"'
        match = re.search(pattern, self.js_content)
        if match:
            return urljoin(self.url,  match.group(1))
        else:
            return None

    def calculate_x(self, x):
        pattern = r'(\w+)"\."width"'
        match = re.search(pattern, x)
        if match:
            modified_x = re.sub(pattern, '1000', x)
            operators = re.findall(r'[\+\-\*/]', modified_x)
            numbers = [num.strip('" ') for num in re.split(r'[\+\-\*/]', modified_x)]
            try:
                numbers = [int(num) for num in numbers]
            except ValueError:
                return None
            result = numbers[0]
            for i in range(len(operators)):
                operator = operators[i]
                next_number = numbers[i + 1]
                if operator == '+':
                    result += next_number
                elif operator == '-':
                    result -= next_number
                elif operator == '*':
                    result *= next_number
                elif operator == '/':
                    if next_number != 0:
                        result /= next_number
            return result
        else:
            return None

    def parse_arts_data(self):
        pattern = r'\{\s*x:\s*[^,]+,\s*y:\s*[^,]+,\s*size:\s*[^,]+,\s*image:\s*\w+,\s*imageData:\s*[^,]+,\s*texture:\s*[^,]+,\s*sprite:\s*[^}]+\}'
        matches = re.findall(pattern, self.js_content, re.DOTALL)
        items_list = []

        for match in matches:
            match = match.replace("null", "None")
            match = re.sub(r'(\w+)', r'"\1"', match)
            match = match.replace("}", "").replace("{", "").strip()
            items_dict = {}
            for item in match.split(","):
                key, value = item.split(":")
                if key.strip().strip('"') == "x" and ("width" in value):
                    x = self.calculate_x(value.strip().strip('"'))
                    items_dict[key.strip().strip('"')] = x
                elif key.strip().strip('"') == "image":
                    image_path = self.parse_image_constants(value.strip().strip('"'))
                    items_dict[key.strip().strip('"')] = image_path
                else:
                    items_dict[key.strip().strip('"')] = value.strip().strip('"')
            items_list.append(items_dict)
        return items_list

    async def get_all_arts_data(self):
        html_content = await self.download_html()
        if html_content:
            js_url = self.find_js_file(html_content)
            if js_url:
                full_js_url = urljoin(self.url, js_url)
                await self.download_js(full_js_url)
                if self.js_content:
                    results = self.parse_arts_data()
                    return results
