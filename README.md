Here is a complete, detailed guide tailored for your project and Termux users, combining best practices for virtual environments, installation, and running your Etsy Social Scraper & Instagram Engagement System on Termux or any Linux-like environment.

Etsy Social Scraper & Instagram Engagement System
A Python-based tool to scrape Etsy seller pages for social media links, analyze Instagram profiles, and automate engagement actions like following and liking posts.

Features
Concurrent Etsy shop scraping with rate limiting

Instagram username similarity search and verification

Automated Instagram follow and like engagement

Retry mechanism for failed URLs

Real-time progress display and performance tracking

Alerting via Telegram and Email for high-priority sellers and errors

Prerequisites
Python 3.7 or higher installed on your system

pip package manager

Basic command-line interface (CLI) knowledge

Internet connection for installing dependencies and running scraper

Installation
1. Clone the repository
bash
git clone <your-repo-url>
cd etsy_scraper
2. (Recommended) Create and activate a virtual environment
Isolating dependencies helps avoid conflicts and keeps your system clean.

On Linux/macOS/Termux:
bash
python3 -m venv venv
source venv/bin/activate
On Windows (PowerShell):
powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
Termux Users (Android) - Important Note
Due to Android storage permission restrictions, creating a virtual environment directly inside shared storage (e.g., /storage/emulated/0/) may fail with permission errors.

Recommended workflow:

Move or copy your project folder to Termux’s home directory:

bash
cp -r /storage/emulated/0/etsy_scraper ~/etsy_scraper
Navigate to the new folder:

bash
cd ~/etsy_scraper
Create and activate the virtual environment here:

bash
python3 -m venv venv
source venv/bin/activate
Install dependencies:

bash
pip install --upgrade pip
pip install -r requirements.txt
Run your project:

bash
python main.py
If you must run from /storage/emulated/0/, you can skip using a virtual environment but risk dependency conflicts and other issues.

3. Install dependencies
bash
pip install --upgrade pip
pip install -r requirements.txt
4. Configure environment variables
Create a .env file in the project root with your credentials and tokens:

text
TELEGRAM_TOKEN=your_telegram_bot_token
EMAIL_USER=your_email_address
EMAIL_PASS=your_email_password
INSTAGRAM_SESSION=your_instagram_session_string
See docs/usage.md for detailed environment variable setup.

Usage
Run the scraper
bash
python main.py
Retry failed URLs
bash
python main.py --retry-failed
Show queue counts without running scraper
bash
python main.py --count-only
Project Structure
text
etsy_scraper/
├── main.py               # Main entry point script
├── scraper/              # Scraper modules and logic
│   ├── __init__.py
│   └── etsy_scraper.py
├── requirements.txt      # Pinned dependencies for installation
├── requirements.in       # Top-level dependencies (for developers)
├── .env                  # Environment variables (not committed)
├── docs/                 # Documentation files
│   ├── usage.md
│   ├── developer_guide.md
│   └── api_reference.md
└── README.md             # This file
Troubleshooting
ModuleNotFoundError or missing packages:
Ensure your virtual environment is activated and dependencies installed correctly.

Permission errors:
Check folder permissions or try running with appropriate privileges.

Issues installing lxml or other C extensions on Android:
Use Termux instead of Pydroid for better compatibility, or fallback to pure Python parsers.

Virtual environment activation problems:
Verify your shell environment and Python installation; on Windows, you may need to adjust execution policies.

Virtual environment creation fails on Android shared storage:
See the Termux Users section above for a workaround by using Termux’s home directory.

About Virtual Environments
A virtual environment is an isolated Python workspace that allows you to manage dependencies per project without affecting global Python installations. This avoids dependency conflicts and keeps your system clean.

Basic commands:

bash
# Create a virtual environment named 'venv'
python3 -m venv venv

# Activate it (Linux/macOS/Termux)
source venv/bin/activate

# Activate it (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install packages inside the virtual environment
pip install -r requirements.txt

# Deactivate the virtual environment
deactivate
Quick Start Summary
For most systems:

bash
git clone <your-repo-url>
cd etsy_scraper
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
For Termux users on Android:

bash
cp -r /storage/emulated/0/etsy_scraper ~/etsy_scraper
cd ~/etsy_scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
Contributing
Contributions are welcome! Please:

Fork the repository

Create a feature branch

Submit pull requests with clear descriptions

License
MIT License © 2025 Univic

Contact
For questions or support, contact:
📧 ilabeshidavid@gmail.com

Thank you for using the Etsy Social Scraper & Instagram Engagement System!
Feel free to open issues or contribute improvements.
