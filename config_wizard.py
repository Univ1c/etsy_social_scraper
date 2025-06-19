import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from dotenv import load_dotenv

def prompt_env_var(prompt_text, default=""):
    value = input(f"{prompt_text} [{default}]: ").strip()
    return value or default

def prompt_int_env_var(prompt_text, default):
    while True:
        value = input(f"{prompt_text} [{default}]: ").strip()
        if value == "":
            return default
        if value.isdigit():
            return int(value)
        print("❌ Please enter a valid number.")

def is_valid_email(email):
    return "@" in email and "." in email

def safe_run(command, cwd=None):
    try:
        subprocess.run(command, check=True, cwd=cwd)
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {' '.join(command)}")
        return False

def setup_virtualenv(project_dir):
    venv_path = project_dir / "venv"
    bin_dir = "Scripts" if os.name == "nt" else "bin"
    python_bin = venv_path / bin_dir / "python"
    pip_bin = venv_path / bin_dir / "pip"

    if not python_bin.exists():
        print("⚙️  Creating virtual environment...")
        if not safe_run(["python3", "-m", "venv", "venv"], cwd=project_dir):
            return False

    print("📦 Installing requirements...")
    return (
        safe_run([str(pip_bin), "install", "--upgrade", "pip"]) and
        safe_run([str(pip_bin), "install", "-r", "requirements.txt"], cwd=project_dir)
    )

def create_env_file(env_path):
    print("🛠️  Welcome to the Etsy Scraper Config Wizard\n")

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    print("📨 EMAIL ALERT SETTINGS")
    print("💡 Gmail users MUST enable 2FA and create an App Password here:")
    print("   👉 https://myaccount.google.com/apppasswords\n")

    email_sender = prompt_env_var("Sender email (e.g. your@gmail.com)", os.getenv("EMAIL_SENDER", ""))
    while email_sender and not is_valid_email(email_sender):
        print("❌ Invalid email format.")
        email_sender = prompt_env_var("Sender email (e.g. your@gmail.com)", os.getenv("EMAIL_SENDER", ""))

    email_password = prompt_env_var("App Password (not your Gmail password)", os.getenv("EMAIL_PASSWORD", ""))
    email_recipient = prompt_env_var("Recipient email for alerts", os.getenv("EMAIL_RECIPIENT", ""))
    while email_recipient and not is_valid_email(email_recipient):
        print("❌ Invalid email format.")
        email_recipient = prompt_env_var("Recipient email for alerts", os.getenv("EMAIL_RECIPIENT", ""))

    print("\n🤖 TELEGRAM ALERT SETTINGS")
    print("💡 Steps to set up Telegram alerts:")
    print("   1. Talk to @BotFather on Telegram to create a bot.")
    print("   2. Copy the bot token given after setup.")
    print("   3. Send a message to your bot, then visit:")
    print("      👉 https://api.telegram.org/bot<YourToken>/getUpdates")
    print("   4. Copy the `chat.id` from the response.\n")

    telegram_token = prompt_env_var("Telegram Bot Token", os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id = prompt_env_var("Telegram Chat ID", os.getenv("TELEGRAM_CHAT_ID", ""))

    print("\n📸 INSTAGRAM LOGIN SETTINGS")
    print("💡 Use a secondary or dedicated Instagram account.")
    print("   This tool automates actions which may trigger Instagram's rate limits.\n")

    insta_user = prompt_env_var("Instagram Username", os.getenv("INSTAGRAM_USERNAME", ""))
    insta_pass = prompt_env_var("Instagram Password", os.getenv("INSTAGRAM_PASSWORD", ""))

    min_gap = prompt_env_var("Min gap between sessions (in hours)", os.getenv("INSTAGRAM_MIN_SESSION_GAP_HOURS", "12"))

    print("\n⚙️ FEATURE TOGGLES")
    print("💡 These control the bot behavior. Enter 'true' or 'false'.\n")

    dry_run = prompt_env_var("Dry run mode? (no real actions)", os.getenv("DRY_RUN", "false"))
    ig_enabled = prompt_env_var("Enable Instagram automation?", os.getenv("INSTAGRAM_ENABLED", "true"))
    follow_enabled = prompt_env_var("Enable follows?", os.getenv("FOLLOW_ENABLED", "true"))
    like_enabled = prompt_env_var("Enable likes?", os.getenv("LIKE_ENABLED", "true"))

    insta_max_daily = prompt_int_env_var("Instagram max daily actions (e.g. 20)", int(os.getenv("INSTAGRAM_MAX_DAILY_ACTIONS", 20)))
    insta_max_likes = prompt_int_env_var("Instagram max likes per shop (e.g. 3)", int(os.getenv("INSTAGRAM_MAX_LIKES", 3)))

    print("\n📂 FILE SETTINGS")
    print("💡 Path to a .txt file containing Etsy shop/product links (one per line).\n")

    input_file = prompt_env_var("Path to Etsy links file", os.getenv("INPUT_FILE", "/storage/emulated/0/links.txt"))

    content = textwrap.dedent(f"""
        EMAIL_SENDER={email_sender}
        EMAIL_PASSWORD={email_password}
        EMAIL_RECIPIENT={email_recipient}

        TELEGRAM_BOT_TOKEN={telegram_token}
        TELEGRAM_CHAT_ID={telegram_chat_id}

        INSTAGRAM_USERNAME={insta_user}
        INSTAGRAM_PASSWORD={insta_pass}

        DRY_RUN={dry_run}
        INSTAGRAM_ENABLED={ig_enabled}
        FOLLOW_ENABLED={follow_enabled}
        LIKE_ENABLED={like_enabled}

        INSTAGRAM_MAX_DAILY_ACTIONS={insta_max_daily}
        INSTAGRAM_MAX_LIKES={insta_max_likes}

        INPUT_FILE={input_file}
    """).strip()

    print("\n🔍 Here's your configuration:")
    print(content)
    confirm = input("\n💾 Save this configuration? (Y/n): ").strip().lower()
    if confirm == "n":
        print("❌ Aborted.")
        return

    env_path.write_text(content + "\n")
    print(f"\n✅ .env successfully saved at: {env_path}")

    if not Path(input_file).exists():
        create_file = input(f"\n⚠️  File not found: {input_file}\nCreate it now? (Y/n): ").strip().lower()
        if create_file != "n":
            Path(input_file).parent.mkdir(parents=True, exist_ok=True)
            Path(input_file).touch()
            print(f"✅ Created empty file: {input_file}")

def parse_flags():
    return {
        "edit": "--edit" in sys.argv,
        "check": "--check" in sys.argv
    }

def main():
    print("🚀 Etsy Scraper Installer for Termux/Linux")
    flags = parse_flags()

    current_dir = Path.cwd()
    is_termux = "com.termux" in os.environ.get("PREFIX", "")
    project_name = "etsy_scraper"

    if flags["check"]:
        print("✅ --check flag detected. Dry test running main.py")
        venv_python = current_dir / "venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
        subprocess.run([str(venv_python), "main.py"])
        return

    if "/storage/emulated/0" in str(current_dir):
        home_dir = Path.home()
        target_dir = home_dir / f".{project_name}"
        print(f"📁 Moving project to secure location: {target_dir}")
        if target_dir.exists():
            confirm = input("⚠️  Target already exists. Overwrite? (y/N): ").strip().lower()
            if confirm != "y":
                print("❌ Aborted.")
                return
            shutil.rmtree(target_dir)
        shutil.copytree(current_dir, target_dir)
        os.chdir(target_dir)
        current_dir = target_dir
        print("✅ Project moved successfully.\n")

    env_path = current_dir / ".env"
    if flags["edit"]:
        if env_path.exists():
            create_env_file(env_path)
        else:
            print("⚠️  No existing .env file found to edit.")
        return

    if env_path.exists():
        confirm = input(f"[!] .env already exists at {env_path}. Overwrite? (y/N): ").strip().lower()
        if confirm != "y":
            print("❌ Skipping .env generation.")
        else:
            create_env_file(env_path)
    else:
        create_env_file(env_path)

    if setup_virtualenv(current_dir):
        print("✅ Environment setup complete.")
        run_now = input("\n▶️  Do you want to run the scraper now? (y/N): ").strip().lower()
        if run_now == "y":
            python_bin = current_dir / "venv" / ("Scripts" if os.name == "nt" else "bin") / "python"
            subprocess.run([str(python_bin), "main.py"])
        else:
            print("👋 All done! To run the bot later, just type:\n   python main.py")
    else:
        print("❌ Failed to set up dependencies.")

if __name__ == "__main__":
    main()
