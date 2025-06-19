"""Manages thread-safe terminal output with timer display and log-friendly formatting."""

import sys
import threading
import logging
from colors import Colors

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr  # Logging goes to stderr
)

class ScreenManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.timer_line = ""
        self.max_line_length = 0

    def print_content(self, message: str) -> None:
        """Safely print a message to stdout, above the timer line."""
        with self.lock:
            self._clear_current_line()
            print(message)
            if self.timer_line:
                self._write_timer_line()

    def update_timer_line(self, timer_message: str) -> None:
        """Update the persistent timer line shown at the bottom of the terminal."""
        with self.lock:
            self.timer_line = timer_message
            self._write_timer_line()

    def clear_timer_line(self) -> None:
        """Clear the current timer line from the screen."""
        with self.lock:
            if self.timer_line:
                self._clear_current_line()
                self.timer_line = ""
                self.max_line_length = 0

    def _write_timer_line(self) -> None:
        """Rewrites the persistent timer line, padded to avoid ghosting."""
        padded = self.timer_line.ljust(self.max_line_length)
        sys.stdout.write(f"\r{padded}\r")
        sys.stdout.flush()
        self.max_line_length = max(self.max_line_length, len(self.timer_line))

    def print_stats(self, stats: dict, header: str = "📊 Runtime Stats", use_color: bool = True) -> None:
        """Prints live runtime statistics above the timer line."""
        with self.lock:
            self._clear_current_line()
            lines = [f"{Colors.BOLD}{header}{Colors.ENDC}"]

            for key, value in stats.items():
                label = f"{key.capitalize().replace('_', ' ')}:"
                value_str = str(value).splitlines()[0]  # Truncate multiline values

                if use_color:
                    lines.append(f"{Colors.OKGREEN}{label:<20} {value_str}{Colors.ENDC}")
                else:
                    lines.append(f"{label:<20} {value_str}")

            sys.stdout.write("\n".join(lines) + "\n")
            if self.timer_line:
                self._write_timer_line()
            sys.stdout.flush()

    def _clear_current_line(self) -> None:
        """Clears the current terminal line."""
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

    def log(self, message: str, level: str = "info") -> None:
        """Convenient logger passthrough with stdout fallback."""
        level = level.lower()
        if level == "warning":
            logging.warning(message)
        elif level == "error":
            logging.error(message)
        else:
            logging.info(message)

# Global instance
SCREEN = ScreenManager()
