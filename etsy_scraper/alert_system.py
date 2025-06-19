"""
Enhanced Alert Notification System with improved security and consistency.

Features:
- Consistent HTML escaping for all output formats
- Configurable message length limits
- Comprehensive error handling with retries
- Type hints for all methods
- Secure credential handling
- Proper async/sync bridging
"""

import os
import asyncio
import smtplib
import time
from typing import Optional, Dict, Literal
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import partial
from telegram import Bot
from telegram.error import TelegramError
from telegram.constants import ParseMode
from screen_manager import SCREEN

# Configurable constants (could be moved to config.py)
MAX_TELEGRAM_MSG_LEN = int(os.getenv("MAX_TELEGRAM_MSG_LEN", 4000))  # Configurable via env
MAX_EMAIL_BODY_LEN = 5000
MAX_SUBJECT_LEN = 100
MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 30]  # Seconds between retries

StatusType = Literal["INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"]

class AlertFormatter:
    """Handles consistent message formatting across all channels."""
    
    _status_colors: Dict[StatusType, str] = {
        "INFO": "#007bff",
        "SUCCESS": "#28a745",
        "WARNING": "#ffc107",
        "ERROR": "#dc3545",
        "CRITICAL": "#721c24"
    }
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Consistent HTML escaping for all output formats."""
        return (text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
    
    @classmethod
    def format_alert(
        cls,
        title: str,
        body: str,
        status: StatusType = "INFO",
        footer_link: Optional[str] = None,
        emoji: str = "🚨"
    ) -> str:
        """Format alert message with consistent HTML escaping."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        color = cls._status_colors.get(status, "#6c757d")
        
        # Escape all content
        safe_title = cls.escape_html(title)
        safe_body = cls.escape_html(body).replace("\n", "<br>")
        safe_emoji = cls.escape_html(emoji)
        
        link_html = ""
        if footer_link:
            safe_link = cls.escape_html(footer_link)
            link_html = f"<br><br><a href='{safe_link}'>🔗 View More</a>"
        
        return (
            f"<b>{safe_emoji} {safe_title}</b><br>"
            f"<i>Status:</i> <code>{status}</code><br>"
            f"<i>Time:</i> {timestamp}<br>"
            f"<hr>{safe_body}{link_html}"
        )
    
    @classmethod
    def format_for_telegram(cls, title: str, body: str) -> str:
        """Telegram-specific formatting with proper escaping."""
        safe_title = cls.escape_html(title)
        safe_body = cls.escape_html(body)
        return f"<b>{safe_title}</b>\n<pre>{safe_body}</pre>"


class AlertSender:
    """Handles the actual sending of alerts with retry logic."""
    
    @staticmethod
    async def _send_telegram_chunk(
        bot: Bot,
        chat_id: str,
        chunk: str,
        attempt: int = 0
    ) -> bool:
        """Send a single Telegram message chunk with retry logic."""
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return True
        except TelegramError as err:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                await asyncio.sleep(delay)
                return await AlertSender._send_telegram_chunk(bot, chat_id, chunk, attempt + 1)
            SCREEN.print_content(f"⚠️ Telegram send failed after {MAX_RETRIES} attempts: {str(err)[:200]}")
            return False
        except Exception as err:
            SCREEN.print_content(f"⚠️ Unexpected Telegram error: {err}")
            return False
    
    @staticmethod
    async def send_telegram_async(message: str) -> bool:
        """Send Telegram alert asynchronously with proper chunking."""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id:
            SCREEN.print_content("⚠️ Telegram alerts not configured")
            return False
        
        # Format and chunk the message
        formatted = AlertFormatter.format_for_telegram("Alert", message)
        chunks = [
            formatted[i:i + MAX_TELEGRAM_MSG_LEN]
            for i in range(0, len(formatted), MAX_TELEGRAM_MSG_LEN)
        ]
        
        bot = Bot(token=token)
        results = await asyncio.gather(*[
            AlertSender._send_telegram_chunk(bot, chat_id, chunk)
            for chunk in chunks
        ])
        
        return all(results)
    
    @staticmethod
    def send_email(subject: str, body: str) -> bool:
        """Send email alert with retry logic."""
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        recipient = os.getenv("EMAIL_RECIPIENT")
        
        if not sender or not password or not recipient:
            SCREEN.print_content("⚠️ Email alerts not configured")
            return False
        
        # Prepare the email
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = recipient
        msg["Subject"] = subject[:MAX_SUBJECT_LEN]
        
        html = f"""
        <html>
        <head><meta charset='UTF-8'></head>
        <body>
        <p style='font-family: Arial; font-size: 14px;'>{body[:MAX_EMAIL_BODY_LEN]}</p>
        </body>
        </html>
        """
        msg.attach(MIMEText(html, "html", "utf-8"))
        
        # Attempt sending with retries
        for attempt in range(MAX_RETRIES):
            try:
                with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(sender, password)
                    server.send_message(msg)
                SCREEN.print_content("📧 Email alert sent successfully")
                return True
            except smtplib.SMTPException as err:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAYS[attempt])
                    continue
                SCREEN.print_content(f"⚠️ Email failed after {MAX_RETRIES} attempts: {str(err)[:200]}")
            except Exception as err:
                SCREEN.print_content(f"⚠️ Unexpected email error: {err}")
        
        return False


class AlertSystem:
    """Public interface for sending alerts through all channels."""
    
    @staticmethod
    def send_telegram(message: str) -> bool:
        """Synchronous wrapper for Telegram alerts."""
        try:
            return asyncio.run(AlertSender.send_telegram_async(message))
        except Exception as err:
            SCREEN.print_content(f"⚠️ Telegram alert failed: {err}")
            return False
    
    @staticmethod
    def send_alerts(
        message: str,
        subject: str,
        alert_type: StatusType = "INFO",
        emoji: str = "🚨",
        footer_link: Optional[str] = None
    ) -> bool:
        """
        Send alerts through all configured channels.
        
        Args:
            message: The alert message content
            subject: Email subject line
            alert_type: Severity level (INFO, SUCCESS, WARNING, ERROR, CRITICAL)
            emoji: Leading emoji for visual emphasis
            footer_link: Optional URL for "View More" link
            
        Returns:
            bool: True if at least one channel succeeded
        """
        if os.getenv("DRY_RUN", "False").lower() == "true":
            SCREEN.print_content("🧪 DRY_RUN enabled. No alerts sent.")
            return False
        
        # Format the message consistently
        formatted = AlertFormatter.format_alert(
            title=subject,
            body=message,
            status=alert_type,
            footer_link=footer_link,
            emoji=emoji
        )
        
        # Send through all channels
        telegram_success = AlertSystem.send_telegram(message)
        email_success = AlertSender.send_email(subject, formatted)
        
        # Brief pause to avoid rate limiting
        time.sleep(2)
        
        return telegram_success or email_success
