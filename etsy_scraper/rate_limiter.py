"""Rate limiting implementation for API requests."""

import time
import threading
import logging
from typing import List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Basic rate limiter that enforces a maximum number of calls
    within a defined time window.
    """

    def __init__(self, max_calls: int, period: float) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_calls (int): Maximum number of allowed calls within the period.
            period (float): Time window in seconds.
        """
        self.max_calls: int = max_calls
        self.period: float = period
        self.calls: List[float] = []
        self.lock = threading.Lock()

    def wait(self) -> None:
        """
        Block execution if the rate limit has been reached.
        Sleeps until the request can proceed.
        """
        with self.lock:
            now = time.monotonic()

            # Clean up timestamps outside the current period
            self.calls = [t for t in self.calls if now - t < self.period]

            # Wait if the rate limit is exceeded
            if len(self.calls) >= self.max_calls:
                wait_time = self.period - (now - self.calls[0])
                if wait_time > 0:
                    logger.info("Rate limit reached. Sleeping for %.1fs...", wait_time)
                    time.sleep(wait_time)
                now = time.monotonic()
                self.calls = [t for t in self.calls if now - t < self.period]

            # Record the current timestamp
            self.calls.append(now)


class SmartRateLimiter:
    """
    Smart rate limiter using real-time and smoothing.
    """

    def __init__(self, max_calls: int, period: float) -> None:
        """
        Initialize the smart rate limiter.

        Args:
            max_calls (int): Maximum number of allowed calls within the period.
            period (float): Time window in seconds.
        """
        self.max_calls = max_calls
        self.period = period
        self.calls: List[float] = []
        self.lock = threading.Lock()
        self.last_call_time = 0.0

    def wait(self) -> None:
        """
        Waits if the rate limit has been reached.
        """
        with self.lock:
            now = time.time()

            # Remove timestamps outside the rate limit window
            self.calls = [t for t in self.calls if now - t < self.period]

            # Wait if the rate limit has been hit
            if len(self.calls) >= self.max_calls and self.calls:
                sleep_time = self.period - (now - self.calls[0])
                if sleep_time > 0:
                    logging.info("Rate limit hit. Sleeping for %.1fs", sleep_time)
                    time.sleep(sleep_time)

                # Recalculate after sleeping
                now = time.time()
                self.calls = [t for t in self.calls if now - t < self.period]

            # Record the new call
            self.calls.append(now)
            self.last_call_time = now


# === GLOBAL RATE LIMITERS ===

# Etsy: Max 12 requests per 60 seconds (but you set 0 to disable)
ETSY_RATE_LIMITER = SmartRateLimiter(0, 5)

# Instagram: Max 25 requests per hour (3600s)
INSTAGRAM_RATE_LIMITER = SmartRateLimiter(25, 3600)
