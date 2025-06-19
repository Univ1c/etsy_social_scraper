"""Main scraping functionality for Etsy social media links."""

# === Standard Libraries ===
import random
import time
import os
import sys
import logging
from threading import Thread, Event
import threading
from typing import Dict, Optional, Tuple, Any, Set
import concurrent.futures

# === Third-Party Libraries ===
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# === Project Modules ===
from config import (
    DRY_RUN,
    INSTAGRAM_ENABLED,
    INSTAGRAM_DELAY,
    RANDOM_DELAY_RANGE,
    SOCIAL_DOMAINS,
    INSTAGRAM_COOLDOWN_INTERVAL,
    MAX_WORKERS,
    TOTAL_PROCESSED,
    TOTAL_PROCESSING_TIME,
    AVG_LOCK,
    WORKER_STATS,
    LAST_INSTAGRAM_ACTION as last_instagram_action
)
from feedback_system import FEEDBACK
from file_operations import mark_done, mark_failed, write_csv_row
from instagram import (
    analyze_instagram_profile
)
from rate_limiter import ETSY_RATE_LIMITER, INSTAGRAM_RATE_LIMITER as instagram_rate_limiter
from screen_manager import SCREEN
from colors import Colors
from alert_system import AlertSystem

logging.basicConfig(level=logging.DEBUG)

USER_AGENT = UserAgent()

OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


NO_SOCIAL_FILE = os.path.join(OUTPUT_DIR, 'no_social_links.txt')


class TemporaryIPBlock(Exception):
    """Raised when IP is blocked or rate-limited by Etsy."""
    pass

def clean_href(href: str) -> str:
    """Clean and normalize href URLs by removing query parameters and trailing slashes.

    Special case: Facebook profile URLs with 'profile.php?id=' retain query parameters.

    Args:
        href: The URL string to clean.

    Returns:
        Cleaned URL string.
    """
    if not href:
        return ''
    if "facebook.com/profile.php?id=" in href:
        return href  # Preserve query params for Facebook profile URLs
    return href.split('?')[0].rstrip('/')


def random_delay(delay_range: Tuple[float, float]) -> None:
    """Sleep for a random duration within given range.
    
    Args:
        delay_range: Tuple of (min_delay, max_delay) in seconds
    """
    time.sleep(random.uniform(*delay_range))


def scrape_social_links(shop_url: str) -> Optional[Dict[str, str]]:
    """Scrape social media links from an Etsy shop page.
    
    Args:
        shop_url: URL of the Etsy shop to scrape
        
    Returns:
        Dictionary mapping social media types to URLs, or None on failure
    """
    logger = logging.getLogger(__name__)
    start_time = time.time()
    
    try:
        headers = {
            'User-Agent': USER_AGENT.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        logger.debug(f"Starting request for {shop_url}")
        random_delay(RANDOM_DELAY_RANGE)
        ETSY_RATE_LIMITER.wait()
        
        try:
            response = requests.get(shop_url, headers=headers, timeout=20)
            logger.debug(f"Got response {response.status_code} for {shop_url}")

            if response.status_code != 200:
                logger.warning(f"Bad status {response.status_code} for {shop_url}")
                mark_failed(shop_url, f"HTTP Status {response.status_code}")
                FEEDBACK.record_processing({
                    'success': False,
                    'processing_time': time.time() - start_time
                })
                return None
                
            response = requests.get(url, headers=HEADERS, timeout=10)

            if response.status_code in [403, 429] or "captcha" in response.text.lower():
                raise TemporaryIPBlock(f"Blocked or rate-limited. Status: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')
            links = {key: '' for key in SOCIAL_DOMAINS}
            found_links = 0

            for anchor in soup.find_all('a', href=True):
                href = anchor['href'].lower()
                for key, domain in SOCIAL_DOMAINS.items():
                    if domain in href:
                        links[key] = clean_href(href)
                        found_links += 1

            FEEDBACK.record_processing({
                'success': True,
                'social_links': found_links,
                'processing_time': time.time() - start_time
            })
            return links

        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request error for {shop_url}: {str(req_err)}")
            mark_failed(shop_url, str(req_err))
            return None

    except Exception as err:
        logger.error(f"Unexpected error processing {shop_url}: {str(err)}", exc_info=True)
        mark_failed(shop_url, str(err))
        return None


def safe_instagram_action(username: Optional[str] = None) -> None:
    """Ensure safe spacing between Instagram API calls and execute actions.
    
    Args:
        username: Instagram username to interact with (optional)
    """
    global last_instagram_action
    
    if not INSTAGRAM_ENABLED:
        return

    with instagram_cooldown:
        elapsed = time.time() - last_instagram_action
        if elapsed < 7:  # Minimum 7 seconds between Instagram actions
            time.sleep(7 - elapsed)
        
        try:
            instagram_rate_limiter.wait()
            last_instagram_action = time.time()
        except Exception as e:
            screen.print_content(f"Instagram rate limiter error: {e}")
            time.sleep(30)  # Longer sleep if rate limiting fails

def process_url(
    url: str,
    idx: int,
    total_urls: int,
    start_time: float,
    processed_ref: Optional[Dict[str, int]] = None,
    avg_time_ref: Optional[Dict[str, float]] = None,
    exiter: Optional[Any] = None,
    stop_event: Optional[threading.Event] = None
) -> float:
    """Process a single Etsy URL to extract social links and handle Instagram analysis."""
    worker_id = threading.get_ident()
    url_start_time = time.time()
    logger = logging.getLogger(__name__)

    # Initialize worker stats
    with AVG_LOCK:
        if worker_id not in WORKER_STATS:
            WORKER_STATS[worker_id] = {
                'last_time': time.time(),
                'last_update': time.time(),
                'avg_time': 0.0,
                'count': 0,
                'active': True
            }
        else:
            WORKER_STATS[worker_id]['active'] = True
            WORKER_STATS[worker_id]['last_time'] = time.time()

    try:
        logger.info(f"Processing URL {idx}/{total_urls}: {url}")
        SCREEN.print_content(f"\n{Colors.OKBLUE}🔗 [{idx}/{total_urls}] Scanning: {url}{Colors.ENDC}")

        def scrape_with_ip_retry(url: str, max_retries: int = 2):
            for attempt in range(max_retries):
                try:
                    return scrape_social_links(url)
                except TemporaryIPBlock as e:
                    SCREEN.print_content(f"🛑 IP Block Detected: {e}")
                    ensure_ip_refresh()  # Prompt user to toggle data
            mark_failed(url, "Blocked after retries")
            return None

        # 🚫 Scrape failed entirely
        if social is None:
            logger.warning(f"Failed to process URL (scrape failed): {url}")
            mark_failed(url, "Scrape failed")
            return 0.0

        # ⚠️ No social links found
        if not any(social.values()):
            logger.info(f"Valid shop with NO social links: {url}")
            mark_no_socials(url)  # Optional: You can define this to save separately
            mark_done(url)
            return 0.0

        # ✅ Has at least one social link
        ig_url = social.get('instagram', '')
        username, last_post, priority, followers = '', '', 'LOW', 0

        if ig_url:
            logger.debug(f"Found Instagram URL: {ig_url}")
            username, last_post, priority, followers = analyze_instagram(ig_url)
        else:
            logger.debug("No Instagram URL found, searching by username")
            username, last_post, priority, followers = find_and_process_instagram_for_etsy(url)

        FEEDBACK.record_processing({
            'success': True,
            'social_links': sum(1 for x in social.values() if x),
            'instagram': bool(username),
            'priority': priority,
            'processing_time': time.time() - url_start_time
        })

        if priority == 'HIGH' and not DRY_RUN:
            logger.info(f"High priority seller found: {url}")
            alert_msg = f"🔥 HIGH PRIORITY SELLER!\nShop: {url}\nIG: https://instagram.com/{username}"
            AlertSystem.send_alerts(alert_msg, "HIGH PRIORITY Etsy Seller")

        if priority in ['HIGH', 'MEDIUM'] and not DRY_RUN and username:
            logger.info(f"Engaging with Instagram account: {username}")
            safe_instagram_action(username)
            random_delay(INSTAGRAM_DELAY)

        write_csv_row([
            url,
            ig_url or (f"https://instagram.com/{username}" if username else ''),
            social.get('facebook', ''),
            social.get('tiktok', ''),
            social.get('pinterest', ''),
            social.get('linktree', ''),
            social.get('youtube', ''),
            social.get('twitch', ''),
            social.get('twitter', ''),
            username,
            last_post,
            priority,
            followers,
            ''
        ])

        mark_done(url)
        logger.info(f"Successfully processed URL: {url}")

    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}", exc_info=True)
        mark_failed(url, str(e))
        return 0.0

    finally:
        processing_time = time.time() - url_start_time
        with AVG_LOCK:
            if processing_time > 0:
                stats = WORKER_STATS[worker_id]
                stats['avg_time'] = (stats['avg_time'] * stats['count'] + processing_time) / (stats['count'] + 1)
                stats['count'] += 1
                stats['last_time'] = time.time()
                stats['active'] = False
                stats['last_update'] = time.time()

                global TOTAL_PROCESSED, TOTAL_PROCESSING_TIME
                TOTAL_PROCESSED += 1
                TOTAL_PROCESSING_TIME += processing_time

            if processed_ref is not None:
                processed_ref['count'] = processed_ref.get('count', 0) + 1
            if avg_time_ref is not None:
                avg_time_ref['value'] = WORKER_STATS[worker_id]['avg_time']
                logger.info(f"Worker {worker_id} updated stats: processed={TOTAL_PROCESSED}, total_time={TOTAL_PROCESSING_TIME:.2f}")

    return processing_time

def save_no_social(url: str):
    """Append URL to the no_social_links.txt file."""
    with open(NO_SOCIAL_FILE, 'a', encoding='utf-8') as f:
        f.write(url + '\n')

def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def live_timer_thread(start_time: float, total_urls: int, stop_event: Event = None) -> None:
    """Continuously updates a live timer and stats line until stopped."""
    while not stop_event or not stop_event.is_set():
        with AVG_LOCK:
            now = time.time()
            elapsed = now - start_time
            processed = TOTAL_PROCESSED

            # Count workers that updated in last 5 seconds and are active
            active_workers = sum(
                1 for w in WORKER_STATS.values()
                if isinstance(w, dict)
                and w.get('active')
                and now - w.get('last_update', 0) < 5
            )

            # Average time per URL (overall)
            avg_time = (TOTAL_PROCESSING_TIME / processed) if processed > 0 else 0

            # Estimate remaining time based on average time * remaining URLs
            remaining = max(0, (total_urls - processed) * avg_time / max(active_workers or 1, 1))

            # Find fastest/slowest worker averages
            worker_times = [
                w['avg_time']
                for w in WORKER_STATS.values()
                if isinstance(w, dict) and w.get('count', 0) > 0
            ]
            fastest = min(worker_times) if worker_times else 0
            slowest = max(worker_times) if worker_times else 0

            # Compose timer status line
            timer_text = (
                f"⏱️ Elapsed: {format_time(elapsed)} | "
                f"Remaining: {format_time(remaining)} | "
                f"Workers: {active_workers}/{MAX_WORKERS} | "
                f"Processed: {processed}/{total_urls} | "
                f"Avg: {avg_time:.1f}s | "
                f"Fastest: {fastest:.1f}s | "
                f"Slowest: {slowest:.1f}s"
            )

            SCREEN.update_timer_line(timer_text)

        time.sleep(1)
