from typing import Dict, Optional, Tuple, Any
import random
import time
import logging
import re
from threading import Event
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from tenacity import retry, wait_exponential, stop_after_attempt
from config import (
    DRY_RUN, INSTAGRAM_ENABLED, INSTAGRAM_DELAY, RANDOM_DELAY_RANGE,
    SOCIAL_DOMAINS, INSTAGRAM_COOLDOWN_INTERVAL, MAX_WORKERS, STATE,
    BASE_DIR, OUTPUT_CSV
)
from feedback_system import FEEDBACK
from file_operations import mark_done, mark_failed, write_csv_row, save_no_social
from instagram import analyze_instagram_profile, engage_with_profile
from rate_limiter import ETSY_RATE_LIMITER, INSTAGRAM_RATE_LIMITER
from screen_manager import SCREEN
from colors import Colors
from alert_system import AlertSystem
from tqdm import tqdm
from pathlib import Path

logger = logging.getLogger(__name__)
USER_AGENT = UserAgent()
NO_SOCIAL_FILE = Path(OUTPUT_CSV).parent / 'no_social_links.txt'

class TemporaryIPBlock(Exception):
    pass

def clean_href(href: str) -> str:
    """Clean an href by removing query parameters and trailing slashes."""
    if not href:
        return ''
    if "facebook.com/profile.php?id=" in href:
        return href
    return href.split('?')[0].rstrip('/')

def random_delay(delay_range: Tuple[float, float]) -> None:
    """Apply a random delay within the specified range."""
    time.sleep(random.uniform(*delay_range))

@retry(wait=wait_exponential(min=4, max=60), stop=stop_after_attempt(5))
def scrape_social_links(shop_url: str) -> Optional[Dict[str, str]]:
    """Scrape social media links from an Etsy shop page."""
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
                'social_links': 0,
                'instagram': False,
                'priority': 'LOW',
                'processing_time': time.time() - start_time
            })
            return None
        if response.status_code in [403, 429] or "captcha" in response.text.lower():
            raise TemporaryIPBlock(f"Blocked or rate-limited. Status: {response.status_code}")
        soup = BeautifulSoup(response.text, 'html.parser')
        links: Dict[str, str] = {key: '' for key in SOCIAL_DOMAINS}
        found_links = 0
        for anchor in soup.find_all('a', href=True):
            href = anchor['href'].lower()
            for key, domain in SOCIAL_DOMAINS.items():
                if domain in href and not links[key]:
                    links[key] = clean_href(href)
                    found_links += 1
        page_text = soup.get_text().lower()
        for key, domain in SOCIAL_DOMAINS.items():
            if domain in page_text and not links[key]:
                pattern = rf'https?://{re.escape(domain)}/[^\s]+'
                matches = re.findall(pattern, page_text)
                if matches:
                    links[key] = clean_href(matches[0])
                    found_links += 1
        FEEDBACK.record_processing({
            'success': True,
            'social_links': found_links,
            'instagram': bool(links.get('instagram')),
            'priority': 'LOW',
            'processing_time': time.time() - start_time
        })
        return links
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Request error for {shop_url}: {req_err}")
        mark_failed(shop_url, str(req_err))
        return None
    except Exception as err:
        logger.error(f"Unexpected error processing {shop_url}: {err}", exc_info=True)
        mark_failed(shop_url, str(err))
        return None

def process_url(
    url: str, idx: int, total_urls: int, start_time: float,
    processed_ref: Optional[Dict[str, int]] = None,
    avg_time_ref: Optional[Dict[str, float]] = None,
    exiter: Optional['GracefulExiter'] = None,
    stop_event: Optional[Event] = None
) -> float:
    """Process a single Etsy shop URL."""
    worker_id = threading.get_ident()
    url_start_time = time.time()
    try:
        logger.info(f"Processing URL {idx}/{total_urls}: {url}")
        SCREEN.print_content(f"\n{Colors.OKBLUE}🔗 [{idx}/{total_urls}] Scanning: {url}{Colors.RESET}")
        social = scrape_social_links(url)
        if social is None:
            logger.warning(f"Failed to process URL (scrape failed): {url}")
            mark_failed(url, "Scrape failed")
            FEEDBACK.record_processing({
                'success': False,
                'social_links': 0,
                'instagram': False,
                'priority': 'LOW',
                'processing_time': time.time() - url_start_time
            })
            return 0.0
        if not any(social.values()):
            logger.info(f"Valid shop with NO social links: {url}")
            save_no_social(url)
            mark_done(url)
            FEEDBACK.record_processing({
                'success': True,
                'social_links': 0,
                'instagram': False,
                'priority': 'LOW',
                'processing_time': time.time() - url_start_time
            })
            return 0.0
        ig_url = social.get('instagram', '')
        username, last_post, priority, followers = '', '', 'LOW', 0
        if ig_url and INSTAGRAM_ENABLED:
            logger.debug(f"Found Instagram URL: {ig_url}")
            username = ig_url.split('instagram.com/')[-1].split('/')[0]
            INSTAGRAM_RATE_LIMITER.wait()  # Handles cooldown via ScraperState
            username, last_post, priority, followers = analyze_instagram_profile({
                'username': username,
                'followers': 0
            })
            if priority in ['HIGH', 'MEDIUM']:
                engage_with_profile(username)
        write_csv_row([
            url, ig_url, social.get('facebook', ''), social.get('tiktok', ''),
            social.get('pinterest', ''), social.get('linktree', ''),
            social.get('youtube', ''), social.get('twitch', ''),
            social.get('twitter', ''), username, last_post, priority, followers, ''
        ])
        mark_done(url)
        logger.info(f"Successfully processed: {url}")
        FEEDBACK.record_processing({
            'success': True,
            'social_links': sum(1 for v in social.values() if v),
            'instagram': bool(ig_url),
            'priority': priority,
            'processing_time': time.time() - url_start_time
        })
    except TemporaryIPBlock as block_err:
        logger.error(f"IP block detected for {url}: {block_err}")
        mark_failed(url, str(block_err))
        AlertSystem.send_alerts(
            message=f"IP block detected while processing {url}: {block_err}",
            subject="IP Block Alert",
            alert_type="ERROR",
            emoji="🚨"
        )
        FEEDBACK.record_processing({
            'success': False,
            'social_links': 0,
            'instagram': False,
            'priority': 'LOW',
            'processing_time': time.time() - url_start_time
        })
        return 0.0
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
        mark_failed(url, str(e))
        FEEDBACK.record_processing({
            'success': False,
            'social_links': 0,
            'instagram': False,
            'priority': 'LOW',
            'processing_time': time.time() - url_start_time
        })
        return 0.0
    finally:
        processing_time = time.time() - url_start_time
        STATE.update_processed(processing_time)
        if processed_ref is not None:
            processed_ref['count'] = processed_ref.get('count', 0) + 1
        if avg_time_ref is not None:
            avg_time_ref['value'] = processing_time
        logger.info(f"Processed {url}: time={processing_time:.2f}s")
    return processing_time

def save_no_social(url: str) -> None:
    """Append URL to the no_social_links.txt file."""
    try:
        with NO_SOCIAL_FILE.open('a', encoding='utf-8') as f:
            f.write(url + '\n')
    except OSError as err:
        logger.error(f"Failed to write to no_social_links.txt: {err}")
        SCREEN.print_content(f"⚠️ Failed to write to no_social_links.txt: {err}")

def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def live_timer_thread(start_time: float, total_urls: int, stop_event: Event = None) -> None:
    """Continuously updates a live timer and stats line with a progress bar."""
    with tqdm(total=total_urls, desc="Processing URLs", unit="url", mininterval=2.0) as pbar:
        while not stop_event or not stop_event.is_set():
            now = time.time()
            elapsed = now - start_time
            processed = STATE.total_processed
            pbar.n = processed
            pbar.refresh()
            active_workers = STATE.active_workers
            avg_time = (STATE.total_processing_time / processed) if processed > 0 else 0
            remaining = max(0, (total_urls - processed) * avg_time / max(active_workers or 1, 1))
            timer_text = (
                f"⏱️ Elapsed: {format_time(elapsed)} | "
                f"Remaining: {format_time(remaining)} | "
                f"Workers: {active_workers}/{MAX_WORKERS} | "
                f"Processed: {processed}/{total_urls} | "
                f"Avg: {avg_time:.1f}s"
            )
            SCREEN.update_timer_line(timer_text)
            time.sleep(2)  # Reduced update frequency
        pbar.n = STATE.total_processed
        pbar.refresh()
