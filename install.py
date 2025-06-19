import os
import subprocess
import sys
from pathlib import Path

CONFIG_WIZARD = "config_wizard.py"
CHECK_UPDATE = "check_update.py"
MAIN_SCRIPT = "main.py"

def clear():
    os.system("clear" if os.name != "nt" else "cls")

def run_script(script, args=""):
    command = f"{sys.executable} {script} {args}"
    subprocess.run(command, shell=True)

def install_dependencies():
    print("📦 Installing dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ All dependencies installed.")

def show_banner():
    print("🛠️  Etsy Scraper & Instagram Engagement System")
    print("=============================================")

def menu():
    while True:
        clear()
        show_banner()
        print("[1] Run Config Wizard (.env setup)")
        print("[2] Install/Update Dependencies")
        print("[3] Run Scraper")
        print("[4] Retry Failed URLs")
        print("[5] Check for Updates")
        print("[6] Exit")
        print("=============================================")
        
        choice = input("Select an option: ").strip()

        if choice == "1":
            run_script(CONFIG_WIZARD)
        elif choice == "2":
            install_dependencies()
            input("\n🔁 Press Enter to return to menu.")
        elif choice == "3":
            run_script(MAIN_SCRIPT)
        elif choice == "4":
            run_script(MAIN_SCRIPT, "--retry-failed")
        elif choice == "5":
            run_script(CHECK_UPDATE)
            input("\n🔁 Press Enter to return to menu.")
        elif choice == "6":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid selection. Try again.")
            input("Press Enter to continue...")

def check_quick_flag():
    return "--quick" in sys.argv

if __name__ == "__main__":
    if check_quick_flag():
        run_script(MAIN_SCRIPT)
    else:
        clear()
        show_banner()
        print("✅ Setup complete! To use the tool, just run:\n   python install.py")
        print("🧰 Use the menu to run the bot, edit config, or check for updates.")
        input("\n🔁 Press Enter to continue to menu...")
        menu()
