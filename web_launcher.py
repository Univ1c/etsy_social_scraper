from flask import Flask, render_template_string, request, redirect, url_for, flash
from pathlib import Path
import os
import subprocess

app = Flask(__name__)
app.secret_key = 'secret'

ENV_PATH = Path("/storage/emulated/0/.env") if Path("/storage/emulated/0/.env").exists() or Path("/storage/emulated/0/").exists() else Path.home() / ".env"

HTML_FORM = """
<!doctype html>
<html>
<head>
  <title>Etsy Scraper Login</title>
</head>
<body style="font-family:sans-serif; max-width:400px; margin:auto; padding-top:40px;">
  <h2>Etsy Social Scraper Login</h2>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <ul style="color:green;">
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
  <form method="POST">
    <label>Instagram Username:</label><br>
    <input name="username" required style="width:100%; padding:5px;"><br><br>

    <label>Instagram Password:</label><br>
    <input type="password" name="password" required style="width:100%; padding:5px;"><br><br>

    <label><input type="checkbox" name="dry_run"> Dry Run (don’t perform actions)</label><br><br>

    <button type="submit" style="padding:10px 20px; background:#4CAF50; color:white; border:none;">Start Scraper</button>
  </form>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        dry_run = request.form.get("dry_run") == "on"

        lines = [
            f"INSTAGRAM_USERNAME={username}",
            f"INSTAGRAM_PASSWORD={password}",
            f"DRY_RUN={'true' if dry_run else 'false'}"
        ]

        with open(ENV_PATH, "w") as f:
            f.write("\n".join(lines))

        flash("Credentials saved. Scraper starting...")

        # Replace this with subprocess or script call as needed
        subprocess.Popen(["python", "main.py"])

        return redirect(url_for("index"))

    return render_template_string(HTML_FORM)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
