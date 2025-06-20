"""
Configuration constants and environment setup for Etsy Social Scraper.
"""

import threading
import time
import os
import random
from os import getenv
from pathlib import Path
from typing import Any, Dict, Tuple

from dotenv import load_dotenv
from fake_useragent import UserAgent

# ========== ENV HELPERS ==========
def get_env_bool(var: str, default="false") -> bool:
    """Convert environment variable to boolean."""
    return getenv(var, default).lower() in ("1", "true", "yes")

def get_env_path(var: str, fallback: Path) -> Path:
    """Get environment variable as Path, with fallback."""
    path = Path(getenv(var)) if getenv(var) else fallback
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        return path
    except Exception as e:
        print(f"[ERROR] Invalid path for {var}: {e}")
        return fallback

# ========== .env LOADING ==========
ENV_PATHS = [
    Path(__file__).resolve().parent.parent / ".env"
]
ENV_LOADED_FROM = None
for env_path in ENV_PATHS:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        ENV_LOADED_FROM = env_path
        break

# ========== BASE DIRECTORY ==========
DEFAULT_STORAGE = Path.home() / "etsy_scraper_data"
MOBILE_STORAGE = Path("/storage/emulated/0/etsy_social_ig_v01/user_files")
BASE_DIR = MOBILE_STORAGE if MOBILE_STORAGE.exists() else DEFAULT_STORAGE
(BASE_DIR / "user_files").mkdir(parents=True, exist_ok=True)

try:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    print(f"[ERROR] Could not create BASE_DIR at {BASE_DIR}: {e}")
    BASE_DIR = Path.home()

# ========== INPUT/OUTPUT FILES ==========
INPUT_FILE = get_env_path("INPUT_FILE", BASE_DIR / "etsy_links.txt")
DONE_FILE = get_env_path("DONE_FILE", BASE_DIR / "done.txt")
FAILED_FILE = get_env_path("FAILED_FILE", BASE_DIR / "failed.txt")
OUTPUT_CSV = get_env_path("OUTPUT_CSV", BASE_DIR / "etsy_social_links.csv")
LOG_FILE = get_env_path("LOG_FILE", BASE_DIR / "scraper.log")
RUNTIME_STATS_FILE = get_env_path("RUNTIME_STATS_FILE", BASE_DIR / "runtime_stats.json")

# ========== TIMING CONFIG ==========
SESSION_ROTATION_INTERVAL = int(getenv("SESSION_ROTATION_INTERVAL", 150))
INSTAGRAM_COOLDOWN_INTERVAL = int(getenv("INSTAGRAM_COOLDOWN", 7))
RANDOM_DELAY_RANGE: Tuple[float, float] = (5.0, 10.0)
INSTAGRAM_DELAY: Tuple[int, int] = (30, 60)

PERFORMANCE_ALERT_THRESHOLD = int(getenv("PERFORMANCE_ALERT_THRESHOLD", 10))
PERFORMANCE_ALERT_INTERVAL_MINUTES = int(getenv("PERFORMANCE_ALERT_INTERVAL_MINUTES", 30))

# ========== FLAGS ==========
DRY_RUN = get_env_bool("DRY_RUN")
INSTAGRAM_ENABLED = get_env_bool("INSTAGRAM_ENABLED", "true")
FOLLOW_ENABLED = get_env_bool("FOLLOW_ENABLED", "true")
LIKE_ENABLED = get_env_bool("LIKE_ENABLED", "true")

# ========== EMAIL / TELEGRAM / SUPPORT ==========
EMAIL_SENDER = getenv("EMAIL_SENDER", "").strip()
EMAIL_PASSWORD = getenv("EMAIL_PASSWORD", "").strip()
EMAIL_RECIPIENT = getenv("EMAIL_RECIPIENT", "").strip()
EMAIL_ENABLED = bool(EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECIPIENT)

TELEGRAM_BOT_TOKEN = getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_USERNAME = getenv("TELEGRAM_USERNAME", "YourTelegramUsername").strip()
WHATSAPP_NUMBER = getenv("WHATSAPP_NUMBER", "2349012345678").strip()
SUPPORT_EMAIL = getenv("SUPPORT_EMAIL", "support@example.com").strip()
SUPPORT_BLOG = getenv("SUPPORT_BLOG", "https://www.example.com").strip()

# ========== INSTAGRAM CREDENTIALS ==========
INSTAGRAM_USERNAME = getenv("INSTAGRAM_USERNAME", "").strip()
INSTAGRAM_PASSWORD = getenv("INSTAGRAM_PASSWORD", "").strip()
INSTAGRAM_CREDENTIALS_SET = bool(INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD)

# ========== ETSY & INSTAGRAM ACTION LIMITS ==========
INSTAGRAM_MAX_LIKES = int(getenv("INSTAGRAM_MAX_LIKES", 5))
INSTAGRAM_MAX_DAILY_FOLLOWS = int(getenv("INSTAGRAM_MAX_DAILY_FOLLOWS", 20))
INSTAGRAM_MIN_SESSION_GAP_HOURS = int(getenv("INSTAGRAM_MIN_SESSION_GAP_HOURS", 12))
ETSY_MAX_CALLS = int(getenv("ETSY_MAX_CALLS", "12"))
INSTAGRAM_MAX_CALLS = int(getenv("INSTAGRAM_MAX_CALLS", "25"))

# ========== WARNINGS ==========
if not INSTAGRAM_CREDENTIALS_SET:
    print("[WARN] Instagram credentials not set. Instagram actions will be disabled.")
if not EMAIL_ENABLED:
    print("[WARN] Email credentials not set. Email alerts will be disabled.")
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    print("[WARN] Telegram credentials not fully set. Telegram alerts will be disabled.")

# ========== SOCIAL DOMAINS ==========
SOCIAL_DOMAINS = {
    'instagram': 'instagram.com',
    'facebook': 'facebook.com',
    'tiktok': 'tiktok.com',
    'pinterest': 'pinterest.com',
    'linktree': 'linktr.ee',
    'youtube': 'youtube.com',
    'twitch': 'twitch.tv',
    'twitter': 'x.com'
}

# ========== THREADING / STATE MANAGEMENT ==========
MAX_WORKERS = 3

class ScraperState:
    """Manages global scraper state."""
    def __init__(self):
        self._lock = threading.Lock()
        self._total_processed = 0
        self._total_processing_time = 0.0
        self._last_instagram_action = time.time()
        self._worker_stats: Dict[int, Dict[str, Any]] = {}
        self._active_workers = 0

    def update_processed(self, processing_time: float) -> None:
        with self._lock:
            self._total_processed += 1
            self._total_processing_time += processing_time
            self._active_workers = sum(
                1 for w in self._worker_stats.values()
                if w.get('active', False) and time.time() - w.get('last_update', 0) < 5
            )

    def update_last_instagram_action(self) -> None:
        with self._lock:
            self._last_instagram_action = time.time()

    def update_worker_stats(self, worker_id: int, stats: Dict[str, Any]) -> None:
        with self._lock:
            self._worker_stats[worker_id] = stats
            self._active_workers = sum(
                1 for w in self._worker_stats.values()
                if w.get('active', False) and time.time() - w.get('last_update', 0) < 5
            )

    @property
    def total_processed(self) -> int:
        with self._lock:
            return self._total_processed

    @property
    def total_processing_time(self) -> float:
        with self._lock:
            return self._total_processing_time

    @property
    def last_instagram_action(self) -> float:
        with self._lock:
            return self._last_instagram_action

    @property
    def worker_stats(self) -> Dict[int, Dict[str, Any]]:
        with self._lock:
            return self._worker_stats.copy()

    @property
    def active_workers(self) -> int:
        with self._lock:
            return self._active_workers

    def reset(self) -> None:
        with self._lock:
            self._total_processed = 0
            self._total_processing_time = 0.0
            self._worker_stats.clear()
            self._active_workers = 0

STATE = ScraperState()

# ========== USER AGENT ==========
fallback_user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari",
    "Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
]
try:
    USER_AGENT = UserAgent()
except Exception as e:
    USER_AGENT = type("MockUA", (), {
        "random": lambda: random.choice(fallback_user_agents)
    })()
    print(f"[WARNING] Failed to initialize UserAgent: {e}")

# ========== ALL EXPORTED ==========
__all__ = [
    "BASE_DIR", "LOG_FILE", "INPUT_FILE", "OUTPUT_CSV", "DONE_FILE", "FAILED_FILE",
    "INSTAGRAM_ENABLED", "FOLLOW_ENABLED", "LIKE_ENABLED", "DRY_RUN",
    "EMAIL_ENABLED", "EMAIL_SENDER", "EMAIL_PASSWORD", "EMAIL_RECIPIENT",
    "INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD", "INSTAGRAM_CREDENTIALS_SET",
    "USER_AGENT", "SESSION_ROTATION_INTERVAL", "INSTAGRAM_COOLDOWN_INTERVAL",
    "RANDOM_DELAY_RANGE", "INSTAGRAM_DELAY", "PERFORMANCE_ALERT_THRESHOLD",
    "PERFORMANCE_ALERT_INTERVAL_MINUTES", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
    "TELEGRAM_USERNAME", "WHATSAPP_NUMBER", "SUPPORT_EMAIL", "SUPPORT_BLOG",
    "MAX_WORKERS", "STATE", "SOCIAL_DOMAINS", "ENV_LOADED_FROM", "RUNTIME_STATS_FILE",
    "INSTAGRAM_MAX_LIKES", "INSTAGRAM_MAX_DAILY_FOLLOWS", "INSTAGRAM_MIN_SESSION_GAP_HOURS",
    "ETSY_MAX_CALLS", "INSTAGRAM_MAX_CALLS"
]

# ========== SETUP TEST ==========
if __name__ == "__main__":
    print(f"📁 BASE_DIR: {BASE_DIR}")
    print(f"📄 INPUT_FILE: {INPUT_FILE}")
    print(f"🚗 DRY_RUN: {DRY_RUN}")
    print(f"📡 INSTAGRAM_ENABLED: {INSTAGRAM_ENABLED}")
    print(f"📬 EMAIL_ENABLED: {EMAIL_ENABLED}")
    print(f"📦 .env loaded from: {ENV_LOADED_FROM}")
