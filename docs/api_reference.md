# API Reference

## main.py

- `run_scraper()`: Orchestrates the scraping workflow.
- `retry_failed_urls()`: Retries URLs from the failed list.
- `process_urls_concurrently()`: Runs concurrent URL processing.
- `GracefulExiter`: Handles SIGINT for graceful shutdown.

## scraping.py

- `scrape_social_links(shop_url)`: Extracts social media links from Etsy shop.
- `process_url(url, idx, total_urls, start_time, ...)`: Processes a single URL.
- `live_timer_thread(...)`: Displays live progress.

## instagram.py

- `analyze_instagram(instagram_url)`: Analyzes Instagram profile activity.
- `find_and_process_instagram_for_etsy_concurrent(etsy_url)`: Finds Instagram accounts related to Etsy shops.
- `follow_and_like(username)`: Follows and likes posts on Instagram.

## feedback_system.py

- `FeedbackSystem`: Tracks scraping performance and problems.
- `record_processing(metrics)`: Records stats per processed URL.
- `generate_performance_report()`: Creates a summary report.

## alert_system.py

- `AlertSystem.send_alerts(message, subject)`: Sends alerts via configured channels.

## file_operations.py

- `load_runtime_stats()`: Loads persistent runtime statistics.
- `save_runtime_stats(stats)`: Saves runtime statistics.
- `mark_done(url)`: Marks URL as processed.
- `mark_failed(url, reason)`: Logs failed URL.

---

For full details, refer to the source code with type hints and docstrings.
