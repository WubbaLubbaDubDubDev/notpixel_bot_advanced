import os
import random
from datetime import datetime, timedelta


class SleepManager:
    def __init__(self, sleep_start_range, sleep_duration_range):
        self.sleep_start_range = sleep_start_range
        self.sleep_duration_range = sleep_duration_range

    def should_sleep(self):
        current_hour = datetime.now().hour
        start_hour, end_hour = self.sleep_start_range

        if start_hour > end_hour:
            return current_hour >= start_hour or current_hour < end_hour
        else:
            return start_hour <= current_hour < end_hour

    def get_wake_up_time(self):
        if not self.should_sleep():
            return None

        random.seed(os.urandom(8))
        sleep_duration = random.uniform(*self.sleep_duration_range)
        sleep_end_time = datetime.now() + timedelta(hours=sleep_duration)
        return sleep_end_time
