# gui_launcher.py

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
import os

ENV_PATH = Path("/storage/emulated/0/.env") if Path("/storage/emulated/0/.env").exists() else Path.home() / ".env"

def save_env(username, password, dry_run):
    lines = [
        f"INSTAGRAM_USERNAME={username}",
        f"INSTAGRAM_PASSWORD={password}",
        f"DRY_RUN={'true' if dry_run else 'false'}"
    ]
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines))
    messagebox.showinfo("Saved", "Credentials saved. You can now run the scraper.")


def on_start():
    username = username_entry.get()
    password = password_entry.get()
    dry_run = dry_run_var.get()

    if not username or not password:
        messagebox.showerror("Missing Info", "Please enter both username and password.")
        return

    save_env(username, password, dry_run)
    root.destroy()
    os.system("python main.py")  # Replace with your actual scraper entry point


root = tk.Tk()
root.title("Etsy Social Scraper Login")
root.geometry("300x220")
root.resizable(False, False)

tk.Label(root, text="Instagram Username:").pack(pady=5)
username_entry = tk.Entry(root, width=30)
username_entry.pack()

tk.Label(root, text="Instagram Password:").pack(pady=5)
password_entry = tk.Entry(root, show="*", width=30)
password_entry.pack()

dry_run_var = tk.BooleanVar()
tk.Checkbutton(root, text="Dry Run (don't perform actions)", variable=dry_run_var).pack(pady=10)

tk.Button(root, text="Start Scraper", command=on_start, bg="#4CAF50", fg="white", padx=10, pady=5).pack()

root.mainloop()