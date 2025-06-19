#!/usr/bin/env python3
"""
MIT License

Copyright (c) 2025 Univic

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""
================================================================================
  Project: Etsy Social Scraper & Instagram Follower & Like Engagement System
  File:    main.py
  Author:  Univic
  Date:    Thursday, 5 June, 2025

  Description:
  ------------------------------------------------------------------------------
  This Python-based tool scrapes Etsy seller pages to extract social media links,
  with a focus on Instagram profiles. It analyzes Instagram accounts for follower
  count and recent activity, and automates engagement actions such as following
  and liking posts to boost social outreach.

  Key Features:
  - Concurrent scraping of Etsy shop social links with rate limiting
  - Instagram username similarity search and verification
  - Automated Instagram follow and like engagement
  - Robust retry mechanism for failed URL processing
  - Real-time progress display and detailed performance tracking
  - Alerting via Telegram and Email for high-priority sellers and errors

  Usage:
  ------------------------------------------------------------------------------
  Run the script with appropriate CLI options:
    - Standard scrape: python main.py
    - Retry failed URLs: python main.py --retry-failed
    - Show queue count: python main.py --count-only

  Configuration:
  ------------------------------------------------------------------------------
  Requires environment variables for Telegram bot, email credentials, and Instagram
  session management. See README for detailed setup instructions.

================================================================================
"""
"""Main entry point for the Etsy scraper application."""

import argparse
import concurrent.futures
import logging
import os
import signal
import sys
import threading
import time
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

# Internal module imports
from config import (
    DRY_RUN,
    INSTAGRAM_DELAY,
    RANDOM_DELAY_RANGE,
    SOCIAL_DOMAINS,
    INSTAGRAM_COOLDOWN_INTERVAL,
    MAX_WORKERS,
    TOTAL_PROCESSED, 
    TOTAL_PROCESSING_TIME, 
    AVG_LOCK, 
    WORKER_STATS,
    LOG_FILE,
    INPUT_FILE,
    OUTPUT_CSV,
    FAILED_FILE,
    DONE_FILE,
    INSTAGRAM_MAX_LIKES
)
from file_operations import (
    load_runtime_stats,
    save_runtime_stats,
    already_processed,
    clean_failed_file,
    count_links_to_scrape,
    mark_done,
    mark_failed,
    read_urls_from_file
)
from feedback_system import FEEDBACK
from scraping import (
    live_timer_thread,
    process_url
)
from screen_manager import SCREEN
from colors import Colors
from alert_system import (
    AlertSystem, 
    AlertFormatter
)

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def show_version():
    try:
        with open("version.txt", "r") as f:
            lines = [line.strip() for line in f if line.strip()]
            latest = lines[-1]
            print(f"\n🔁 Etsy Scraper Version: {latest}\n")
    except Exception as e:
        print("⚠️ Version info missing or unreadable.")

class GracefulExiter:
    """Handles graceful shutdown on SIGINT (Ctrl+C)."""
    def __init__(self):
        self._should_exit = False
        self._lock = threading.Lock()
        self._event = threading.Event()
        signal.signal(signal.SIGINT, self.exit_gracefully)
        self.logger = logging.getLogger(__name__)

    @property
    def should_exit(self):
        with self._lock:
            return self._should_exit

    def exit_gracefully(self, signum, frame) -> None:
        """Set flag to True when SIGINT is received."""
        with self._lock:
            if not self._should_exit:
                self._should_exit = True
                self._event.set()
                self.logger.info("Graceful exit initiated by SIGINT")
                SCREEN.print_content(f"{Colors.WARNING}\n⚠️ Graceful shutdown initiated...{Colors.ENDC}")
                # Force immediate exit on second SIGINT
                signal.signal(signal.SIGINT, lambda s, f: os._exit(1))

    def wait_for_exit(self, timeout=None):
        """Wait for exit signal (blocking with optional timeout)."""
        return self._event.wait(timeout)

def format_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}"

def calculate_runtime_stats(runtime_stats: Dict[str, float]) -> Tuple[float, float]:
    """Calculate average processing time and estimated time for pending URLs."""
    total_processed = runtime_stats.get('total_urls_processed', 0)
    total_time = runtime_stats.get('total_processing_time', 0.0)
    pending = runtime_stats.get('pending_urls', 0)

    avg = (total_time / total_processed) if total_processed else 0.0
    return avg, avg * pending

def initialize_scraper() -> Tuple[int, Dict[str, float]]:
    """Initialize runtime state and print initial stats."""
    os.system('cls' if os.name == 'nt' else 'clear')
    SCREEN.print_content(f"{Colors.HEADER}=== ETSY SOCIAL LINK SCRAPER ==={Colors.ENDC}")

    total_to_scrape = count_links_to_scrape()
    SCREEN.print_content(f"{Colors.OKBLUE}📊 Total URLs to scrape: {total_to_scrape}{Colors.ENDC}")

    runtime_stats = load_runtime_stats()
    runtime_stats['pending_urls'] = total_to_scrape

    avg, est_total = calculate_runtime_stats(runtime_stats)
    if avg > 0:
        SCREEN.print_content(
            f"{Colors.OKCYAN}⏱️ Historical avg: {avg:.2f}s | "
            f"Estimated total: {format_time(est_total)}{Colors.ENDC}"
        )

    return total_to_scrape, runtime_stats

def process_urls_concurrently(
    urls: Set[str],
    start_time: float,
    exiter: GracefulExiter,
    processed_ref: Optional[Dict[str, int]] = None,
    avg_time_ref: Optional[Dict[str, float]] = None
) -> None:
    """Process URLs concurrently with live feedback and graceful exit support."""
    stop_event = threading.Event()
    timer_thread = threading.Thread(
        target=live_timer_thread,
        args=(start_time, len(urls)),
        daemon=True
    )
    timer_thread.start()

    with AVG_LOCK["avg"]:
        WORKER_STATS.clear()
        TOTAL_PROCESSED = 0
        TOTAL_PROCESSING_TIME = 0.0

    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="Worker"
        ) as executor:
            futures = {
                executor.submit(
                    process_url,
                    url,
                    idx,
                    len(urls),
                    start_time,
                    processed_ref,
                    avg_time_ref,
                    exiter,
                    stop_event
                ): url
                for idx, url in enumerate(urls, 1)
                if not exiter.should_exit and not already_processed(url)
            }

            for future in concurrent.futures.as_completed(futures):
                if exiter.should_exit or stop_event.is_set():
                    break
                try:
                    future.result(timeout=120)
                except concurrent.futures.TimeoutError:
                    logger.warning("URL processing timed out.")
                except Exception as e:
                    logger.error(f"URL processing failed: {e}")

    except Exception as e:
        logger.critical(f"Unexpected failure during concurrent processing: {e}")
        raise

    finally:
        stop_event.set()
        timer_thread.join(timeout=2)

def run_scraper(exiter: GracefulExiter) -> None:
    """Main function to run the scraper with full workflow."""
    try:
        total_to_scrape, runtime_stats = initialize_scraper()
        
        if total_to_scrape == 0 or exiter.should_exit:
            SCREEN.print_content("ℹ️ No new URLs to process")
            return

        html_msg = AlertFormatter.format_alert(
            title="Startup Confirmation",
            body="Script started successfully — alert systems working!",
            status="SUCCESS",
            emoji="🔄"
        )

        AlertSystem.send_alerts(
            html_msg,
            "Script Startup Test"
        )

        urls = read_urls_from_file(INPUT_FILE)
        if not urls or exiter.should_exit:
            SCREEN.print_content("ℹ️ No new URLs to process")
            return

        start_time = time.time()
        process_urls_concurrently(urls, start_time, exiter)

        if FEEDBACK.stats['successful'] > 0 and not exiter.should_exit:
            runtime_stats['total_processing_time'] += TOTAL_PROCESSING_TIME
            runtime_stats['total_urls_processed'] += FEEDBACK.stats['successful']
            save_runtime_stats(runtime_stats)

        if not exiter.should_exit:
            if not exiter.should_exit:
                contact_links = (
        "Scraper finished with issues.<br><br>"
        "🛠️ <a href='mailto:ilabeshidavid@gmail.com?subject=Scraper%20Feedback'>Email Support</a><br>"
        "📘 <a href='https://www.blogger.com/'>Visit Blog</a><br>"
        "📨 <a href='https://t.me/YourTelegramUsername'>Telegram</a><br>"
        "📱 <a href='https://wa.me/2349012345678?text=Hi%2C%20need%20assistance%20with%20the%20Etsy%20tool'>WhatsApp</a>"
    )

                html_msg = AlertFormatter.format_alert(
                    title="Scrape Completed",
                    body=contact_links,
                    status="WARNING",
                    emoji="🧩"
    )

                AlertSystem.send_alerts(
                    message=html_msg,
                    subject="Final Scrape Report"
    )
            display_final_report()

    except Exception as err:
        logger.critical(f"Fatal error in scraper: {err}", exc_info=True)
        html_msg = AlertFormatter.format_alert(
            title="Scraper Error",
            body=str(err),
            status="CRITICAL",
            footer_link=None,
            emoji="🚨"
)

        AlertSystem.send_alerts(
            html_msg,
            "Scraper Failure Alert"
        )
        raise

def display_final_report() -> None:
    """Display final summary report after scraping completes."""
    SCREEN.print_content(f"\n{Colors.HEADER}📊 FINAL REPORT{Colors.ENDC}")
    SCREEN.print_content(FEEDBACK.generate_performance_report())
    SCREEN.print_content(f"{Colors.OKGREEN}✅ CSV Saved: {OUTPUT_CSV}{Colors.ENDC}")
    SCREEN.print_content(f"{Colors.WARNING}⚠️ Failed URLs logged: {FAILED_FILE}{Colors.ENDC}")

    if not DRY_RUN:
        html_msg = AlertFormatter.format_alert(
            title="Scrape Summary",
            body=FEEDBACK.generate_performance_report(),
            status="SUCCESS",
            emoji="📊"
        )

        AlertSystem.send_alerts(
            html_msg,
            "Etsy Scrape Completion Report"
        )

def retry_failed_urls(exiter: GracefulExiter) -> Tuple[int, int, int]:
    """Retry processing URLs listed in failed.txt file."""
    try:
        if not FAILED_FILE.exists():
            SCREEN.print_content("No failed.txt file found")
            return 0, 0, 0

        urls_to_retry = get_failed_urls()
        if not urls_to_retry or exiter.should_exit:
            SCREEN.print_content("All failed URLs have already been processed successfully")
            return 0, 0, 0

        retry_count = len(urls_to_retry)
        SCREEN.print_content(f"\n🔁 Preparing to retry {retry_count} failed URLs")
        FEEDBACK.record_retry()

        runtime_stats = load_runtime_stats()
        display_retry_estimate(runtime_stats, retry_count)

        start_time = time.time()
        processed_ref = {'count': 0}
        avg_time_ref = {'value': (
            runtime_stats['total_processing_time'] / runtime_stats['total_urls_processed']
            if runtime_stats['total_urls_processed'] > 0
            else 0
        )}

        process_urls_concurrently(urls_to_retry, start_time, exiter, processed_ref, avg_time_ref)
        
        if not exiter.should_exit:
            clean_failed_file()

        success_count = processed_ref['count']
        fail_count = retry_count - success_count

        if success_count > 0 and not exiter.should_exit:
            runtime_stats['total_processing_time'] += TOTAL_PROCESSING_TIME
            runtime_stats['total_urls_processed'] += success_count
            save_runtime_stats(runtime_stats)

        if not exiter.should_exit:
            display_retry_summary(retry_count, success_count, fail_count)

        return success_count, fail_count, retry_count
    except Exception as err:
        logger.error(f"Error in retry_failed_urls: {err}", exc_info=True)
        raise

def get_failed_urls() -> Set[str]:
    """Extract and validate URLs from failed.txt."""
    with open(FAILED_FILE, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    urls_to_retry = set()
    for line in lines:
        try:
            if line.startswith('['):
                url = line.split('] ')[1].split(' | ')[0].strip()
            else:
                url = line.strip()

            if not url or not url.startswith(('http://', 'https://')):
                logger.warning(f"Skipping invalid URL: {line.strip()}")
                continue

            if not already_processed(url):
                urls_to_retry.add(url)
        except Exception as err:
            logger.warning(f"Failed to parse line: {line.strip()} - {err}")

    return urls_to_retry

def display_retry_estimate(runtime_stats: Dict[str, float], retry_count: int) -> None:
    """Display estimated retry time based on historical data."""
    if runtime_stats['total_urls_processed'] > 0:
        historical_avg = runtime_stats['total_processing_time'] / runtime_stats['total_urls_processed']
        est_total = historical_avg * retry_count
        SCREEN.print_content(f"⏱️ Estimated retry time: {format_time(est_total)}")

def display_retry_summary(retry_count: int, success_count: int, fail_count: int) -> None:
    """Display summary of retry operation results."""
    retry_report = (
        f"\n🔄 RETRY SUMMARY\n"
        f"Total attempted: {retry_count}\n"
        f"✅ Successfully processed: {success_count}\n"
        f"❌ Failed again: {fail_count}\n"
        f"Success rate: {success_count / retry_count * 100:.1f}%"
    )
    SCREEN.print_content(retry_report)

    if not DRY_RUN and retry_count > 0:
        html_msg = AlertFormatter.format_alert(
            title="Retry Summary",
            body=retry_report,
            status="INFO",
            emoji="🔁"
        )

        AlertSystem.send_alerts(
            html_msg,
            "Etsy Retry Completion Report"
        )

def display_queue_status() -> None:
    """Display current queue status and exit."""
    pending = count_links_to_scrape()
    failed = 0
    if FAILED_FILE.exists():
        with open(FAILED_FILE, 'r', encoding='utf-8') as file:
            failed = len([line for line in file.readlines() if line.strip()])
    
    SCREEN.print_content("\n📊 Queue Status:")
    SCREEN.print_content(f"New URLs to scrape: {pending}")
    SCREEN.print_content(f"Failed URLs to retry: {failed}")

    runtime_stats = load_runtime_stats()
    if runtime_stats['total_urls_processed'] > 0:
        avg_time = runtime_stats['total_processing_time'] / runtime_stats['total_urls_processed']
        est_total = avg_time * (pending + failed)
        SCREEN.print_content(f"\n⏱️ Estimated total runtime: {format_time(est_total)}")

def worker_health_check():
    while True:
        with AVG_LOCK:
            now = time.time()
            inactive_workers = [
                wid for wid, stats in WORKER_STATS.items()
                if now - stats['last_time'] > 30 and stats.get('active', False)
            ]
            if inactive_workers:
                logger.warning(f"Inactive workers detected: {inactive_workers}")
        time.sleep(30)


def backup_user_files_once_per_day_zip(retain_days=30):
    try:
        project_root = Path(__file__).resolve().parent
        src = project_root / "user_files"
        backups_dir = project_root / "backups"
        backups_dir.mkdir(exist_ok=True)

        today_tag = datetime.now().strftime("%Y%m%d")
        zip_backup_path = backups_dir / f"user_files_backup_{today_tag}.zip"

        # Create today's backup if not already present
        if not zip_backup_path.exists():
            with zipfile.ZipFile(zip_backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in src.rglob("*"):
                    if file_path.is_file():
                        zipf.write(file_path, arcname=file_path.relative_to(src))

        # Cleanup old backups
        cutoff = datetime.now() - timedelta(days=retain_days)
        for zip_file in backups_dir.glob("user_files_backup_*.zip"):
            try:
                date_str = zip_file.stem.rsplit("_", 1)[-1]
                file_date = datetime.strptime(date_str, "%Y%m%d")
                if file_date < cutoff:
                    zip_file.unlink()
            except Exception:
                continue
    except Exception:
        pass  # Silent fail

def main() -> None:
    """Entry point for command-line execution."""
    show_version()
    exiter = GracefulExiter()

    try:
        parser = argparse.ArgumentParser(
            description="Etsy Social Scraper & Instagram Engagement System"
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='Retry URLs from failed.txt'
        )
        parser.add_argument(
            '--count-only',
            action='store_true',
            help='Show count of URLs to process and exit'
        )
        args = parser.parse_args()

        if args.count_only:
            display_queue_status()
            sys.exit(0)
        
        if args.retry_failed:
            success, fails, total = retry_failed_urls(exiter)
            if not exiter.should_exit:
                FEEDBACK.send_performance_alert()
        else:
            run_scraper(exiter)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received in main")
        sys.exit(1)
    except Exception as err:
        logger.critical(f"Application error: {err}", exc_info=True)
        SCREEN.print_content(f"{Colors.FAIL}🚨 Critical error: {err}{Colors.ENDC}")
        sys.exit(1)
    finally:
        if exiter.should_exit:
            logger.info("Application exited gracefully")
            SCREEN.print_content(f"{Colors.WARNING}🛑 Graceful shutdown complete{Colors.ENDC}")
            sys.exit(0)

if __name__ == "__main__":
    main()
