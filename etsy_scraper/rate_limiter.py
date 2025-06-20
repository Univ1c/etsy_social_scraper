"""Rate limiting implementation for API requests."""

import time
import threading
from typing import List
from screen_manager import SCREEN
from config import STATE, ETSY_MAX_CALLS, INSTAGRAM_MAX_CALLS
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for API requests with thread-safe operations."""

    def __init__(self, max_calls: int, period: float) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_calls: Maximum number of allowed calls within the period.
            period: Time window in seconds.
        """
        self.max_calls: int = max_calls
        self.period: float = period
        self.calls: List[float] = []
        self.lock: threading.Lock = threading.Lock()
        self.last_call_time: float = 0.0

    def reset(self) -> None:
        """Reset the rate limiter's call history."""
        with self.lock:
            self.calls = []
            self.last_call_time = 0.0

    def wait(self) -> None:
        """Wait if the rate limit is reached."""
        with self.lock:
            now = time.time()
            self.calls = [t for t in self.calls if now - t < self.period]

            if len(self.calls) >= self.max_calls and self.calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    logger.info(f"Rate limit hit. Sleeping for {sleep_time:.1f}s")
                    SCREEN.print_content(f"⏳ Rate limit hit. Sleeping for {sleep_time:.1f}s")
                    time.sleep(sleep_time)

                now = time.time()
                self.calls = [t for t in self.calls if now - t < self.period]

            self.calls.append(now)
            self.last_call_time = now
            if self is INSTAGRAM_RATE_LIMITER:
                STATE.update_last_instagram_action()


ETSY_RATE_LIMITER = RateLimiter(ETSY_MAX_CALLS, 60)
INSTAGRAM_RATE_LIMITER = RateLimiter(INSTAGRAM_MAX_CALLS, 3600)
