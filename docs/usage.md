# Usage Guide

## Installation

1. Clone the repository:
git clone <your-repo-url>

text
2. Install dependencies:
pip install -r requirements.txt

text
3. Set up environment variables for Telegram, Email, and Instagram session as described in the README.

## Running the Scraper

- To start scraping:
python main.py

text

- To retry failed URLs:
python main.py --retry-failed

text

- To see queue counts without running:
python main.py --count-only

text

## Configuration

- Edit `config.py` or set environment variables to customize:
- Rate limits
- Instagram session file
- Alerting credentials
- Delay timings
- Output file paths

## Output

- Results are saved in a CSV file (`output.csv` by default).
- Failed URLs are logged in `failed.txt`.
- Real-time progress and stats are displayed in the terminal.

---

For detailed developer information, see the [Developer Guide](developer_guide.md).