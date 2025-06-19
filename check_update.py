import requests

REMOTE_VERSION_URL = "https://raw.githubusercontent.com/univ1c/etsy_social_ig_v01/main/VERSION.txt"
LOCAL_VERSION_FILE = "VERSION.txt"

def fetch_remote_version():
    try:
        response = requests.get(REMOTE_VERSION_URL, timeout=5)
        if response.status_code == 200:
            return response.text.strip()
    except Exception as e:
        print(f"❌ Error checking remote version: {e}")
    return None

def fetch_local_version():
    try:
        with open(LOCAL_VERSION_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.0.0"

def main():
    print("🔎 Checking for updates...")
    remote_version = fetch_remote_version()
    local_version = fetch_local_version()

    if remote_version:
        if remote_version != local_version:
            print(f"🚀 Update available! Current: {local_version}, Latest: {remote_version}")
            print("📥 Visit: https://github.com/YOUR_USERNAME/YOUR_REPO to download the latest version.")
        else:
            print("✅ You are using the latest version.")
    else:
        print("⚠️ Could not check for updates.")

if __name__ == "__main__":
    main()
