[![Static Badge](https://img.shields.io/badge/Telegram-Bot%20Link-Link?style=for-the-badge&logo=Telegram&logoColor=white&logoSize=auto&color=blue)](https://t.me/notpixel/app?startapp=f411905106)

## ⚡⚡ Get 3x rewards with fully automatic art parsing and smart pixel selection 🆕 ⚡⚡



## Recommendation before use

## 🔥🔥 Use PYTHON 3.10 🔥🔥

## Features  
| Feature                                                                                                                  | Supported |
|--------------------------------------------------------------------------------------------------------------------------|:---------:|
| Asynchronous processing                                                                                                  |     ✅     |
| Proxy binding to session                                                                                                 |     ✅     |
| User-Agent binding to session                                                                                            |     ✅     |
| Support pyrogram .session                                                                                                |     ✅     |
| Registration in bot                                                                                                      |     ✅     |
| Auto-tasks                                                                                                               |     ✅     |
| Daily rewards                                                                                                            |     ✅     |
| Drawing specified image 🆕                                                                                               |     ✅     |
| Fully automatic art parsing and smart pixel selection 🆕                                                                 |     ✅     |
| Automatically binds available proxies to new sessions 🆕                                                                 |     ✅     |
| Automatically binds random device parameters (such as Android device model, version, and app version) to new sessions 🆕 |     ✅     |
| Automatically selects the least popular template for painting to maximize the chances of earning a 3x reward 🆕          |     ✅     |
| Night mode, which puts the script to sleep during a defined period for a specified duration 🆕                           |     ✅     |
| Action randomization 🆕                                                                                                  |     ✅     |

## Settings  
| **Parameter**                   | **Description**                                                            |
|---------------------------------|:---------------------------------------------------------------------------|
| **API_ID / API_HASH**           | Your API_ID / API_HASH                                                     |
| **SLEEP_TIME**                  | Sleep time between cycles (default - [426, 4260])                          |
| **NIGHT_MODE**                  | Enable night mode to avoid actions during specified hours (default - True) |
| **NIGHT_SLEEP_START_HOURS**     | Night sleep start hours (default - [22, 2])                                |
| **NIGHT_SLEEP_DURATION**        | Duration of night sleep in hours (default - [4, 8])                        |
| **START_DELAY**                 | Delay before starting actions (default - [30, 60])                         |
| **AUTO_TASK** DANGEROUS         | Automatically execute tasks (default - False)                              |
| **TASKS_TO_DO** AUTOTASK        | List of tasks to perform automatically                                     |
| **AUTO_DRAW**                   | Enable automatic pixel drawing (default - True)                            |
| **JOIN_TG_CHANNELS**            | Automatically join Telegram channels (default - True)                      |
| **CLAIM_REWARD**                | Automatically claim rewards (default - True)                               |
| **AUTO_UPGRADE**                | Automatically upgrade items or settings (default - True)                   |
| **JOIN_SQUAD**                  | Automatically join squad (default - True)                                  |
| **USE_SECRET_WORDS**            | Enable secret words usage (default - True)                                 |
| **SECRET_WORDS**                | List of secret words                                                       |
| **REF_ID**                      | Referral ID                                                                |
| **IN_USE_SESSIONS_PATH**        | Path to the file where used sessions are stored                            |
| **AUTO_BIND_PROXIES_FROM_FILE** | Automatically bind proxies from file (default - False)                     |
| **DRAW_IMAGE**                  | Perform image drawing (default - False)                                    |
| **DRAWING_START_COORDINATES**   | Starting coordinates for drawing (default - [0, 0])                        |
| **IMAGE_PATH**                  | Path to the image file for drawing (default - "10x10.png")                 |
| **PALETTE**                     | List of colors used for drawing                                            |
| **DAW_MAIN_TEMPLATE**           | Enable 3x rewards (default - True)                                         |
| **USE_UNPOPULAR_TEMPLATE**      | Use an unpopular template for drawing (default - True)                     |
| **USE_SPECIFIED_TEMPLATES**     | Enable using a predefined list of templates for drawing (default - False)  |
| **SPECIFIED_TEMPLATES_ID_LIST** | List of template IDs to use when **USE_SPECIFIED_TEMPLATES** is enabled    |


## Quick Start 📚

To quickly install libraries and run the bot - open `run.bat` on Windows or `run.sh` on Linux.

## Prerequisites
Before you begin, make sure you have the following installed:
- [Python](https://www.python.org/downloads/) **version 3.10**

## Obtaining API Keys
1. Go to my.telegram.org and log in using your phone number.
2. Select "API development tools" and fill out the form to register a new application.
3. Record the `API_ID` and `API_HASH` provided after registering your application in the `.env` file.

## Installation
You can download the [**repository**](https://github.com/WubbaLubbaDubDubDev/notpixel_bot_advanced) by cloning it to your system and installing the necessary dependencies:
git clone https://github.com/WubbaLubbaDubDubDev/notpixel_bot_advanced


Then you can do automatic installation by typing:

### Windows:
```shell
./run.bat
```

### Linux:
```shell
chmod +x run.sh
./run.sh
```

### Running in Docker

To run the project in Docker, navigate to the root directory of the script and execute the following command:
```shell
docker-compose up --build
```

## Linux manual installation
```shell
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
cp .env-example .env
nano .env  # Here you must specify your API_ID and API_HASH, the rest is taken by default
python3 main.py
# 1 - Run clicker
# 2 - Creates a session
```

## Windows manual installation
```shell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env-example .env
# Here you must specify your API_ID and API_HASH, the rest is taken by default
python main.py
# 1 - Run clicker
# 2 - Creates a session
```

## Usages
During the first launch of the bot, create a session for it using the "Creates a session" command. This will create a "sessions" folder where all accounts will be stored, along with an accounts.json file containing the configurations. If you already have sessions, simply place them in the "sessions" folder and run the clicker. During startup, you will be able to configure the use of a proxy for each session. User-Agent is automatically generated for each account.

If you want the proxies to be automatically bound to each new session, set the AUTO_BIND_PROXIES_FROM_FILE parameter to True. In this case, a unique proxy will be selected for each session during the first launch, and if there are not enough proxies for all sessions, they will be used again. Make sure to upload your proxies to the proxies.txt file located in the /bot/config folder in the format type://user:pass@ip:port before doing this.

Here are the two supported formats for the accounts.json file:

### Simple Format:
```shell
[
  {
    "session_name": "name_example",
    "user_agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
    "proxy": "type://user:pass@ip:port"
  }
]
```

### Recommended Format (applies to all newly created sessions):
```shell
[
  {
    "session_name": "name_example",
    "user_agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.6422.165 Mobile Safari/537.36",
    "proxy": "type://user:pass@ip:port"
    "android_device": "SM-A525F",
    "android_version": "14",
    "app_version": "Telegram Android 10.14.0"
  }
]
```

"proxy": "" - if you don't use a proxy

The recommended format should be used for all new sessions, as it allows associating each session with a specific device matching the User-Agent. This helps avoid situations where the User-Agent represents one type of device (e.g., a Google Pixel smartphone), while the session itself is registered on another (e.g., Windows).