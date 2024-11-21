import random
import re

from bot.config.device_performance import device_performance
from bot.config.telegram_versions import versions

existing_versions = {
    110: [
        '110.0.5481.154',
        '110.0.5481.153',
        '110.0.5481.65',
        '110.0.5481.64',
        '110.0.5481.63',
        '110.0.5481.61'
    ],
    111: [
        "111.0.5563.116",
        '111.0.5563.115',
        '111.0.5563.58',
        '111.0.5563.49'
    ],
    112: [
        '112.0.5615.136',
        '112.0.5615.136',
        '112.0.5615.101',
        '112.0.5615.100',
        '112.0.5615.48'
    ],
    113: [
        '113.0.5672.77',
        '113.0.5672.76'
    ],
    114: [
        '114.0.5735.60',
        '114.0.5735.53'
    ],
    115: [
        '115.0.5790.136'
    ],
    116: [
        '116.0.5845.172',
        '116.0.5845.164',
        '116.0.5845.163',
        '116.0.5845.114',
        '116.0.5845.92'
    ],
    117: [
        '117.0.5938.154',
        '117.0.5938.141',
        '117.0.5938.140',
        '117.0.5938.61',
        '117.0.5938.61',
        '117.0.5938.60'
    ],
    118: [
        '118.0.5993.112',
        '118.0.5993.111',
        '118.0.5993.80',
        '118.0.5993.65',
        '118.0.5993.48'
    ],
    119: [
        '119.0.6045.194',
        '119.0.6045.193',
        '119.0.6045.164',
        '119.0.6045.163',
        '119.0.6045.134',
        '119.0.6045.134',
        '119.0.6045.66',
        '119.0.6045.53'
    ],
    120: [
        '120.0.6099.230',
        '120.0.6099.210',
        '120.0.6099.194',
        '120.0.6099.193',
        '120.0.6099.145',
        '120.0.6099.144',
        '120.0.6099.144',
        '120.0.6099.116',
        '120.0.6099.116',
        '120.0.6099.115',
        '120.0.6099.44',
        '120.0.6099.43'
    ],
    121: [
        '121.0.6167.178',
        '121.0.6167.165',
        '121.0.6167.164',
        '121.0.6167.164',
        '121.0.6167.144',
        '121.0.6167.143',
        '121.0.6167.101'
    ],
    122: [
        '122.0.6261.119',
        '122.0.6261.106',
        '122.0.6261.105',
        '122.0.6261.91',
        '122.0.6261.90',
        '122.0.6261.64',
        '122.0.6261.43'
    ],
    123: [
        '123.0.6312.121',
        '123.0.6312.120',
        '123.0.6312.119',
        '123.0.6312.118',
        '123.0.6312.99',
        '123.0.6312.80',
        '123.0.6312.41',
        '123.0.6312.40'
    ],
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
        '126.0.6478.122',
        '126.0.6478.72',
        '126.0.6478.71',
        '126.0.6478.50'
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
