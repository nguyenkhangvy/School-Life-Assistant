"""Logging to %LOCALAPPDATA%\\SchoolLifeAssistant\\agent.log with secrets scrubbed.

Every secret the agent handles is registered with protect(); any log line,
including error tracebacks, has those values replaced with ***.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sla_agent.state import agent_home

_secrets = set()
_handlers = []  # handlers added by setup_logging
MIN_SECRET_LENGTH = 4  # shorter values would blank out ordinary text


def protect(secret):
    if secret and len(secret) >= MIN_SECRET_LENGTH:
        _secrets.add(secret)


def redact(text):
    for secret in sorted(_secrets, key=len, reverse=True):
        text = text.replace(secret, "***")
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        return redact(super().format(record))


def setup_logging(home=None):
    """Log to agent.log (and to the console when there is one). Returns the log file path."""
    home = Path(home) if home else agent_home()
    home.mkdir(parents=True, exist_ok=True)
    path = home / "agent.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Calling this again (e.g. main() twice in one process) replaces, not duplicates.
    while _handlers:
        old = _handlers.pop()
        root.removeHandler(old)
        old.close()

    file_handler = RotatingFileHandler(path, maxBytes=500_000, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(file_handler)
    _handlers.append(file_handler)

    # The scheduled task runs without a console (pythonw), where sys.stderr is None.
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.WARNING)
        console.setFormatter(RedactingFormatter("%(levelname)s: %(message)s"))
        root.addHandler(console)
        _handlers.append(console)
    return path
