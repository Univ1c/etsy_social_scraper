# Developer Guide

## Project Structure

- `main.py`: Entry point with CLI and orchestration.
- `scraping.py`: Core Etsy scraping and Instagram profile processing.
- `instagram.py`: Instagram API client and engagement logic.
- `feedback_system.py`: Tracks performance metrics and detected issues.
- `alert_system.py`: Sends alerts via Telegram and Email.
- `file_operations.py`: Handles file reading/writing and runtime stats.
- `rate_limiter.py`: Implements rate limiting for APIs.
- `screen_manager.py`: Thread-safe terminal output management.
- `colors.py`: Terminal color codes for formatting.

## Key Concepts

- **Concurrency**: Uses `ThreadPoolExecutor` with rate limiting to balance speed and API limits.
- **Resilience**: Robust error handling and retry logic.
- **Alerting**: Multi-channel alert system for high-priority events.
- **Performance Tracking**: Real-time stats and post-run reports.

## Extending the Project

- Add new social media scrapers by extending `scraping.py`.
- Support additional alert channels in `alert_system.py`.
- Integrate unit tests in a new `tests/` directory.

---

Refer to the [API Reference](api_reference.md) for detailed module and function documentation.
