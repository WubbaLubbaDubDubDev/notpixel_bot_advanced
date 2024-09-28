from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    SLEEP_TIME: list[int] = [360, 3600]
    START_DELAY: list[int] = [5, 25]
    AUTO_TASK: bool = True
    TASK_TO_DO: list[str] = ["x:notcoin", "x:notpixel", "paint20pixels", "leagueBonusSilver", "invite3frens",
                              "leagueBonusGold"]
    AUTO_DRAW: bool = True
    JOIN_TG_CHANNELS: bool = True
    CLAIM_REWARD: bool = True
    AUTO_UPGRADE: bool = True
    REF_ID: str = 'f411905106'
    IGNORED_BOOSTS: list[str] = ['INVITE_FRIENDS', 'TON_TRANSACTION', 'BOOST_CHANNEL', 'ACTIVITY_CHALLENGE',
                                 'CONNECT_WALLET']


settings = Settings()
