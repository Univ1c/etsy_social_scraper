"""File handling utilities for the scraper."""

import csv
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Dict, Any, List

from config import DONE_FILE, FAILED_FILE, INPUT_FILE, OUTPUT_CSV, RUNTIME_STATS_FILE
from screen_manager import SCREEN

FILE_LOCK = threading.Lock()

# Centralized CSV headers to avoid duplication
CSV_HEADERS = [
    "etsy_url", "instagram_url", "facebook_url", "tiktok_url",
    "pinterest_url", "linktree_url", "youtube_url", "twitch_url", "twitter_url",
    "username", "last_post_date", "priority", "follower_count", "notes"
]

def read_urls_from_file(file_path: Path) -> Set[str]:
    """
    Read Etsy shop URLs from the input file.

    Args:
        file_path (Path): Path to the file containing URLs.

    Returns:
        Set[str]: A set of cleaned URLs.
    """
    urls = set()
    if not file_path.exists():
        SCREEN.print_content(f"Input file {file_path} does not exist.")
        return urls

    try:
        with file_path.open('r', encoding='utf-8') as file:
            for line in file:
                url = line.strip()
                if url and url.startswith(('http://', 'https://')):
                    urls.add(url)
    except OSError as err:
        SCREEN.print_content(f"Failed to read URLs from file: {err}")

    return urls

def get_processed_urls() -> Set[str]:
    """
    Get all URLs that have already been processed from the output CSV.

    Returns:
        Set[str]: Set of processed URLs
    """
    processed = set()
    if not OUTPUT_CSV.exists():
        return processed

    try:
        with FILE_LOCK, OUTPUT_CSV.open('r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames and 'etsy_url' in reader.fieldnames:
                processed = {row['etsy_url'] for row in reader if row.get('etsy_url')}
    except (OSError, csv.Error) as err:
        SCREEN.print_content(f"Error reading processed URLs: {err}")

    return processed

def already_processed(url: str) -> bool:
    """
    Check if a URL has already been processed and exists in the output CSV.

    Args:
        url (str): The Etsy shop URL to check.

    Returns:
        bool: True if the URL has already been processed, False otherwise.
    """
    return url in get_processed_urls()

def mark_failed(shop_url: str, reason: str = "Unknown Error") -> None:
    """
    Mark a URL as failed by writing it to the failed file with a timestamp and reason.
    """
    try:
        with FILE_LOCK:
            file_exists = OUTPUT_CSV.exists()
            with OUTPUT_CSV.open('a', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                if not file_exists:
                    writer.writerow(CSV_HEADERS)
                row_data = [shop_url] + [""] * 13 + [reason]
                writer.writerow(row_data)
    except OSError as err:
        SCREEN.print_content(f"Failed to write CSV row: {err}")

def clean_failed_file() -> None:
    """
    Remove successfully processed URLs from the failed log file.
    """
    if not FAILED_FILE.exists():
        return

    try:
        with FAILED_FILE.open('r', encoding='utf-8') as file:
            failed_lines = file.readlines()

        processed_urls = get_processed_urls()
        
        with FAILED_FILE.open('w', encoding='utf-8') as file:
            for line in failed_lines:
                url = (
                    line.split('] ')[1].split(' | ')[0]
                    if line.startswith('[')
                    else line.strip()
                )
                if url not in processed_urls:
                    file.write(line)
    except OSError as err:
        SCREEN.print_content(f"Failed to clean failed file: {err}")

def write_csv_row(row_data: List[str]) -> None:
    """
    Write a row of data to the output CSV file.

    Args:
        row_data (List[str]): A list representing one row of data to be written.
    """
    file_exists = OUTPUT_CSV.exists()

    try:
        with OUTPUT_CSV.open('a', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            if not file_exists:
                writer.writerow(CSV_HEADERS)
            writer.writerow(row_data)
    except OSError as err:
        SCREEN.print_content(f"Failed to write CSV row: {err}")

def mark_done(shop_url: str) -> None:
    """
    Mark a URL as successfully processed by appending it to the done file.

    Args:
        shop_url (str): The URL to mark as done.
    """
    try:
        with DONE_FILE.open('a', encoding='utf-8') as file:
            file.write(f"{shop_url.strip()}\n")
    except OSError as err:
        SCREEN.print_content(f"Failed to mark URL as done: {err}")

def count_links_to_scrape() -> int:
    """
    Count the number of unique Etsy shop URLs remaining to be scraped.

    Returns:
        int: The count of unique pending URLs.
    """
    if not INPUT_FILE.exists():
        SCREEN.print_content("❌ Input file not found")
        return 0

    try:
        with INPUT_FILE.open('r', encoding='utf-8') as file:
            lines = file.readlines()

        done_urls: Set[str] = set()
        if DONE_FILE.exists():
            with DONE_FILE.open('r', encoding='utf-8') as file:
                done_urls = {line.strip() for line in file.readlines()}

        processed_urls = get_processed_urls()
        unique_urls: Set[str] = set()

        for line in lines:
            url = line.strip().split()[0]
            if (url and url not in done_urls 
                and url not in processed_urls 
                and '✔️' not in line):
                unique_urls.add(url)

        return len(unique_urls)

    except OSError as err:
        SCREEN.print_content(f"Failed to count links: {err}")
        return 0

def load_runtime_stats() -> Dict[str, Any]:
    """
    Load runtime statistics from the stats JSON file.

    Returns:
        dict: A dictionary with keys like 'total_processing_time' and 'total_urls_processed'.
    """
    try:
        if RUNTIME_STATS_FILE.exists():
            with RUNTIME_STATS_FILE.open('r', encoding='utf-8') as file:
                return json.load(file)
    except (OSError, json.JSONDecodeError) as err:
        SCREEN.print_content(f"Error loading runtime stats: {err}")

    return {'total_processing_time': 0.0, 'total_urls_processed': 0}

def save_runtime_stats(stats: Dict[str, Any]) -> None:
    """
    Save runtime statistics to the stats JSON file.

    Args:
        stats (dict): A dictionary of stats to be saved.
    """
    try:
        RUNTIME_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with RUNTIME_STATS_FILE.open('w', encoding='utf-8') as file:
            json.dump(stats, file)
    except (OSError, TypeError) as err:
        SCREEN.print_content(f"⚠️ Failed to save runtime stats: {err}")
