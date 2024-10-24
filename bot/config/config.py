from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    # Timing and delays settings
    SLEEP_TIME: list[int] = [426, 4260]  # Sleep time in seconds

    NIGHT_MODE: bool = True
    NIGHT_SLEEP_START_HOURS: list[int] = [22, 2]
    NIGHT_SLEEP_DURATION: list[int] = [4, 8]
    START_DELAY: list[int] = [30, 60]  # Delay before starting

    # Task automation
    AUTO_TASK: bool = False  # Automatic task execution
    TASKS_TO_DO: list[str] = [  # Tasks to perform
        "paint20pixels", "x:notpixel",
        "x:notcoin", "channel:notcoin",
        "channel:notpixel_channel"
    ]
    AUTO_DRAW: bool = True  # Enable automatic drawing
    JOIN_TG_CHANNELS: bool = True  # Join Telegram channels
    CLAIM_REWARD: bool = True  # Automatically claim rewards
    AUTO_UPGRADE: bool = True  # Automatically upgrade

    # Referral settings
    REF_ID: str = 'f411905106'  # Referral ID

    # Session and proxy handling
    IN_USE_SESSIONS_PATH: str = 'app_data/used_sessions.txt'  # Path to used sessions file
    AUTO_BIND_PROXIES_FROM_FILE: bool = False  # Automatically bind proxies from file

    # Drawing and image settings
    DRAW_IMAGE: bool = False  # Perform image drawing
    DRAWING_START_COORDINATES: list[int] = [0, 0]  # Starting coordinates for drawing
    IMAGE_PATH: str = "10x10.png"  # Path to the image for drawing

    # Color palette
    PALETTE: list[str] = [  # Colors for drawing
        "#E46E6E", "#FFD635", "#7EED56", "#00CCC0", "#51E9F4",
        "#94B3FF", "#E4ABFF", "#FF99AA", "#FFB470", "#FFFFFF",
        "#BE0039", "#FF9600", "#00CC78", "#009EAA", "#3690EA",
        "#6A5CFF", "#B44AC0", "#FF3881", "#9C6926", "#898D90",
        "#6D001A", "#bf4300", "#00A368", "#00756F", "#2450A4",
        "#493AC1", "#811E9F", "#a00357", "#6D482F", "#000000"]

    # Additional settings
    ENABLE_3X_REWARD: bool = True  # Enable 3x rewards
    USE_UNPOPULAR_TEMPLATE: bool = True  # Use an unpopular template


settings = Settings()
