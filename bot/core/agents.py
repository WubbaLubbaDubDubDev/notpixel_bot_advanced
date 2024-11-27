import random
import re

from bot.config.device_performance import device_performance
from bot.config.telegram_versions import versions

existing_versions = {
    124: [
        '124.0.6367.179',
        '124.0.6367.172',
        '124.0.6367.171',
        '124.0.6367.114',
        '124.0.6367.113',
        '124.0.6367.83',
        '124.0.6367.82',
        '124.0.6367.54'
    ],
    125: [
        '125.0.6422.165',
        '125.0.6422.164',
        '125.0.6422.147',
        '125.0.6422.146',
        '125.0.6422.113',
        '125.0.6422.72',
        '125.0.6422.72',
        '125.0.6422.53',
        '125.0.6422.52'
    ],
    126: [
        '126.0.6478.186',
        '126.0.6478.122',
        '126.0.6478.72',
        '126.0.6478.71',
        '126.0.6478.50'
    ],
    127: [
        '127.0.6533.106',
        '127.0.6533.103',
        '127.0.6533.84',
        '127.0.6533.64'
    ],
    128: [
        '128.0.6613.146',
        '128.0.6613.127',
        '128.0.6613.99'
    ],
    129: [
        '129.0.6668.100',
        '129.0.6668.81',
        '129.0.6668.71'
    ],
    130: [
        '130.0.6723.103',
        '130.0.6723.102',
        '130.0.6723.86',
        '130.0.6723.59',
        '130.0.6723.58',
        '130.0.6723.40'
    ],
    131: [
        '131.0.6778.81',
        '131.0.6778.39'
    ]
}

android_sdk_mapping = {
    "7.0": 24,
    "7.1": 25,
    "8.0": 26,
    "8.1": 27,
    "9.0": 28,
    "10.0": 29,
    "11.0": 30,
    "12.0": 31,
    "13.0": 33,
    "14.0": 34,
    "15.0": 35
}


def _extract_device_name(user_agent):
    device_names = []
    for performance in device_performance.keys():
        device_names.extend(device_performance[performance])

    for device in device_names:
        if device in user_agent:
            return device
    return None


def _get_android_version(user_agent: str) -> None | str:
    android_version_pattern = re.compile(r'Android (\d+\.\d+)')
    match = android_version_pattern.search(user_agent)

    if match:
        return match.group(1)
    else:
        return None


def generate_random_user_agent():
    major_version = random.choice(list(existing_versions.keys()))
    browser_version = random.choice(existing_versions[major_version])
    device_perf = random.choice(list(device_performance.keys()))
    android_device = random.choice(device_performance[device_perf])
    android_version = random.choice(list(android_sdk_mapping.keys()))
    sdk_version = android_sdk_mapping[android_version]
    telegram_version = random.choice(versions)

    user_agent = _get_user_agent(browser_version, android_version, sdk_version, android_device,
                                 telegram_version, device_perf)

    return user_agent, android_version, android_device, telegram_version


def update_useragent(old_useragent, telegram_version=None, android_version=None, android_device=None):
    if telegram_version is None:
        telegram_version = random.choice(versions)

    if android_version is None:
        android_version = _get_android_version(old_useragent)
        if android_version is None:
            android_version = random.choice(list(android_sdk_mapping.keys()))

    device_perf = random.choice(list(device_performance.keys()))

    if android_device is None:
        android_device = _extract_device_name(old_useragent)
        if android_device is None:
            android_device = random.choice(device_performance[device_perf])

    major_version = random.choice(list(existing_versions.keys()))
    browser_version = random.choice(existing_versions[major_version])
    sdk_version = android_sdk_mapping[android_version]

    return _get_user_agent(browser_version, android_version, sdk_version, android_device, telegram_version,
                           device_perf)


def _get_user_agent(browser_version, android_version, sdk_version, android_device, telegram_version, device_perf):
    return (f"Mozilla/5.0 (Linux; Android {android_version}; {android_device}) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{browser_version} Mobile Safari/537.36 Telegram-Android/{telegram_version} ({android_device}; "
            f"Android {android_version}; SDK {sdk_version}; {device_perf})")
