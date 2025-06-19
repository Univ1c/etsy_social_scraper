"""Tracks scraping performance metrics and detected problems."""
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from alert_system import (
    AlertSystem, 
    AlertFormatter
)
from colors import Colors
from config import (
    DRY_RUN,
    PERFORMANCE_ALERT_THRESHOLD,
    PERFORMANCE_ALERT_INTERVAL_MINUTES,
)


class FeedbackSystem:
    """Performance tracking and problem detection with thread-safe operations."""

    def __init__(self) -> None:
        self.session_start: datetime = datetime.now()
        self._lock = threading.Lock()
        self.stats: Dict[str, int] = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'with_social': 0,
            'with_instagram': 0,
            'high_priority': 0,
            'medium_priority': 0,
            'low_priority': 0,
            'actions_taken': 0,
            'retries': 0
        }
        self.performance_metrics: Dict[str, Any] = {
            'avg_processing_time': 0.0,
            'fastest_process': float('inf'),
            'slowest_process': 0.0,
            'start_time': self.session_start,
            'last_alert': None
        }
        self.problems_detected: List[Dict[str, str]] = []

    def record_processing(self, metrics: Dict[str, Any]) -> None:
        with self._lock:
            self.stats['total'] += 1
            if metrics.get('success', True):
                self.stats['successful'] += 1
                if metrics.get('social_links', 0) > 0:
                    self.stats['with_social'] += 1
                if metrics.get('instagram', False):
                    self.stats['with_instagram'] += 1
                    priority = metrics.get('priority', 'LOW').upper()
                    if priority in ['HIGH', 'MEDIUM', 'LOW']:
                        self.stats[f"{priority.lower()}_priority"] += 1
            else:
                self.stats['failed'] += 1

            processing_time: float = metrics.get('processing_time', 0.0)
            if processing_time > 0 and self.stats['total'] > 0:
                prev_avg: float = self.performance_metrics['avg_processing_time']
                total: int = self.stats['total']
                self.performance_metrics['avg_processing_time'] = (
                    (prev_avg * (total - 1)) + processing_time
                ) / total
                self.performance_metrics['fastest_process'] = min(
                    self.performance_metrics['fastest_process'], processing_time
                )
                self.performance_metrics['slowest_process'] = max(
                    self.performance_metrics['slowest_process'], processing_time
                )

            self._check_performance_alert()

    def record_action(self, action_type: str) -> None:
        with self._lock:
            self.stats['actions_taken'] += 1

    def record_retry(self) -> None:
        with self._lock:
            self.stats['retries'] += 1

    def detect_problem(self, problem_description: str) -> None:
        with self._lock:
            self.problems_detected.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'description': problem_description
            })

    def get_session_duration(self) -> timedelta:
        return datetime.now() - self.performance_metrics['start_time']

    def generate_performance_report(self) -> str:
        with self._lock:
            duration: timedelta = self.get_session_duration()
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)

            success_percent = (
                self.stats['successful'] / self.stats['total'] * 100
                if self.stats['total'] > 0 else 0.0
            )
            fail_percent = (
                self.stats['failed'] / self.stats['total'] * 100
                if self.stats['total'] > 0 else 0.0
            )

            report = (
                f"📈 PERFORMANCE REPORT\n"
                f"--------------------------\n"
                f"⏱️ Duration: {int(hours)}h {int(minutes)}m {int(seconds)}s\n"
                f"📊 URLs Processed: {self.stats['total']}\n"
                f"✅ Successful: {self.stats['successful']} ({success_percent:.1f}%)\n"
                f"❌ Failed: {self.stats['failed']} ({fail_percent:.1f}%)\n\n"
                f"🔗 Links Found:\n"
                f"  - With any social: {self.stats['with_social']}\n"
                f"  - With Instagram: {self.stats['with_instagram']}\n"
                f"  - High Priority: {self.stats['high_priority']}\n"
                f"  - Medium Priority: {self.stats['medium_priority']}\n"
                f"  - Low Priority: {self.stats['low_priority']}\n\n"
                f"⚡ Performance:\n"
                f"  - Avg Time: {self.performance_metrics['avg_processing_time']:.2f}s\n"
                f"  - Fastest: {self.performance_metrics['fastest_process']:.2f}s\n"
                f"  - Slowest: {self.performance_metrics['slowest_process']:.2f}s\n\n"
                f"🛠️ Actions: {self.stats['actions_taken']}\n"
                f"🔁 Retries: {self.stats['retries']}"
            )

            if self.problems_detected:
                report += "\n\n⚠️ Recent Issues:\n"
                for problem in self.problems_detected[-5:]:
                    report += f"  - [{problem['timestamp']}] {problem['description']}\n"

            return report.strip()

    def send_performance_alert(self) -> None:
        if not DRY_RUN and self.stats['total'] > 0:
            report_text: str = self.generate_performance_report()
            subject: str = f"Performance Report - {self.stats['total']} URLs processed"

            # HTML version for email
            html_report = format_alert_html(
                title="📈 Performance Summary",
                body=report_text,
                status="INFO"
            )

            # HTML version for Telegram
            telegram_html = format_alert_for_telegram(
                title="📈 Performance Summary",
                body=report_text
            )

            AlertSystem.send_alerts(
                email_html=html_report,
                telegram_html=telegram_html,
                subject=subject
            )

            with self._lock:
                self.performance_metrics['last_alert'] = datetime.now()

    def _check_performance_alert(self) -> None:
        if not PERFORMANCE_ALERT_THRESHOLD:
            return

        last_alert = self.performance_metrics['last_alert']
        now = datetime.now()

        if self.stats['total'] % PERFORMANCE_ALERT_THRESHOLD == 0:
            if (last_alert is None or 
                (now - last_alert).total_seconds() >= 
                PERFORMANCE_ALERT_INTERVAL_MINUTES * 60):
                self.send_performance_alert()


FEEDBACK: FeedbackSystem = FeedbackSystem()
