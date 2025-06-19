# etsy_scraper/scraping.py
from typing import Dict, Optional, Tuple, Any
import random
import time
import os
import logging
from threading import Event
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, wait_exponential, stop_after_attempt
from config import (
    DRY_RUN, INSTAGRAM_ENABLED, INSTAGRAM_DELAY, RANDOM_DELAY_RANGE,
    SOCIAL_DOMAINS, INSTAGRAM_COOLDOWN_INTERVAL, MAX_WORKERS,
    TOTAL_PROCESSED, TOTAL_PROCESSING_TIME, AVG_LOCK, WORKER_STATS,
    LAST_INSTAGRAM_ACTION
)
from feedback_system import FEEDBACK
from file_operations import mark_done, mark_failed, write_csv_row
from instagram import analyze_instagram_profile
from rate_limiter import ETSY_RATE_LIMITER
from screen_manager import SCREEN
from colors import Colors
from alert_system import AlertSystem

logging.basicConfig(level=logging.DEBUG)
USER_AGENT = UserAgent()
OUTPUT_DIR = os.path.join(os.getcwd(), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
NO_SOCIAL_FILE = os.path.join(OUTPUT_DIR, 'no_social_links.txt')

class TemporaryIPBlock(Exception):
    pass

def clean_href(href: str) -> str:
    if not href:
        return ''
    if "facebook.com/profile.php?id=" in href:
        return href
    return href.split('?')[0].rstrip('/')

def random_delay(delay_range: Tuple[float, float]) -> None:
    time.sleep(random.uniform(*delay_range))

@retry(wait=wait_exponential(min=4, max=60), stop=stop_after_attempt(5))
def scrape_social_links(shop_url: str) -> Optional[Dict[str, str]]:
    logger = logging.getLogger(__name__)
    start_time = time.time()
    headers = {
        'User-Agent': USER_AGENT.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    try:
        logger.debug(f"Starting request for {shop_url}")
        random_delay(RANDOM_DELAY_RANGE)
        ETSY_RATE_LIMITER.wait()
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
    url: str, idx: int, total_urls: int, start_time: float,
    processed_ref: Optional[Dict[str, int]] = None,
    avg_time_ref: Optional[Dict[str, float]] = None,
    exiter: Optional[Any] = None, stop_event: Optional[threading.Event] = None
) -> float:
    worker_id = threading.get_ident()
    url_start_time = time.time()
    logger = logging.getLogger(__name__)
    with AVG_LOCK["avg"]:
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
        social = scrape_social_links(url)
        if social is None:
            logger.warning(f"Failed to process URL (scrape failed): {url}")
            mark_failed(url, "Scrape failed")
            return 0.0
        if not any(social.values()):
            logger.info(f"Valid shop with NO social links: {url}")
            with open(NO_SOCIAL_FILE, 'a', encoding='utf-8') as f:
                f.write(url + '\n')
            mark_done(url)
            return 0.0
        ig_url = social.get('instagram', '')
        username, last_post, priority, followers = '', '', 'LOW', 0
        if ig_url and INSTAGRAM_ENABLED:
            logger.debug(f"Found Instagram URL: {ig_url}")
            username, last_post, priority, followers = analyze_instagram_profile({
                'username': ig_url.split('instagram.com/')[-1].split('/')[0],
                'followers': 0
            })
        write_csv_row([
            url, ig_url, social.get('facebook', ''), social.get('tiktok', ''),
            social.get('pinterest', ''), social.get('https', ''),  # Fix: Changed 'linktree' to 'https' (likely typo)
            social.get('youtube', ''), social.get('twitch', ''),
            social.get('twitter', ''), username, last_post, priority, followers, ''
        ])
        mark_done(url)
        logger.info(f"Successfully processed: {url}")
    except Exception as e:
        logger.error(f"Error processing URL {url}: {str(e)}")
        mark_failed(url, str(e))
        return 0.0
    finally:
        processing_time = time.time() - url_start_time
        with AVG_LOCK["avg"]:
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
        with AVG_LOCK["avg"]:
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
