"""Terminal color codes for formatted output."""

class Colors:
    # pylint: disable=too-few-public-methods
    """ANSI escape sequences for terminal text formatting."""

    HEADER = '\033[95m'      # Purple/Magenta
    OKBLUE = '\033[94m'      # Blue
    OKCYAN = '\033[96m'      # Cyan
    OKGREEN = '\033[92m'     # Green
    WARNING = '\033[93m'     # Yellow
    FAIL = '\033[91m'        # Red
    RESET = '\033[0m'        # Reset to default
    BOLD = '\033[1m'         # Bold
    UNDERLINE = '\033[4m'    # Underline
    ENDC = '\033[0m'  # Alias for RESET

    @staticmethod
    def wrap(text: str, color: str) -> str:
        """Wrap text in ANSI color codes."""
        return f"{color}{text}{Colors.RESET}"
