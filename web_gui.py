import streamlit as st
from pathlib import Path
import subprocess
import os

# Set .env file location
ENV_FILE = Path("/storage/emulated/0/.env") if Path("/storage/emulated/0/").exists() else Path.home() / ".env"

st.title("📦 Etsy Social Scraper Setup")

st.subheader("🔒 Instagram Settings")
instagram_enabled = st.checkbox("Enable Instagram", value=True)
instagram_username = st.text_input("Username", type="default")
instagram_password = st.text_input("Password", type="password")

st.subheader("📣 Telegram Alerts")
telegram_bot_token = st.text_input("Bot Token")
telegram_chat_id = st.text_input("Chat ID")

st.subheader("📁 Input & Output")
input_file = st.text_input("Input File Path", "/storage/emulated/0/etsy_links.txt")
output_csv = st.text_input("Output CSV Path", "/storage/emulated/0/etsy_social_links.csv")

st.subheader("⚙️ Advanced Settings")
dry_run = st.checkbox("Dry Run Mode")
session_interval = st.number_input("Session Rotation Interval (seconds)", min_value=30, value=150)
cooldown = st.number_input("Instagram Cooldown (seconds)", min_value=1, value=7)

if st.button("💾 Save Config"):
    with open(ENV_FILE, "w") as f:
        f.write(f"INSTAGRAM_ENABLED={instagram_enabled}\n")
        f.write(f"INSTAGRAM_USERNAME={instagram_username.strip()}\n")
        f.write(f"INSTAGRAM_PASSWORD={instagram_password.strip()}\n")
        f.write(f"TELEGRAM_BOT_TOKEN={telegram_bot_token.strip()}\n")
        f.write(f"TELEGRAM_CHAT_ID={telegram_chat_id.strip()}\n")
        f.write(f"INPUT_FILE={input_file.strip()}\n")
        f.write(f"OUTPUT_CSV={output_csv.strip()}\n")
        f.write(f"DRY_RUN={dry_run}\n")
        f.write(f"SESSION_ROTATION_INTERVAL={session_interval}\n")
        f.write(f"INSTAGRAM_COOLDOWN={cooldown}\n")

    st.success(f"✅ Saved to {ENV_FILE}")

if st.button("🚀 Start Scraper Now"):
    st.info("Launching scraper...")
    # Replace with actual command or script
    subprocess.Popen(["python", "main.py"])
    st.success("Scraper launched in background.")
