"""
Provides logging utilities for consistent formatting across the codebase.
Primary features:
- Custom formatter that adds ANSI colors to log levels
- Timezone-aware timestamps with local offset
- Standardized log format: "LEVEL [logger.name] [YYYY-MM-DD HH:MM:SS±ZZZZ] message"


Usage:

```python
from datacommons.api.core.logging import get_logger

logger = get_logger(__name__)

logger.info("Hello, world!")
# Output: "INFO [datacommons.api.core.logging] [2021-01-01 12:00:00+0000] Hello, world!"
```

"""

import logging
import sys
from datetime import datetime

# ANSI escape sequences
_RESET = "\033[0m"
_LEVEL_COLORS = {
  "DEBUG":    "\033[36m", # Cyan
  "INFO":     "\033[32m", # Green
  "WARNING":  "\033[33m", # Yellow
  "ERROR":    "\033[31m", # Red
  "CRITICAL": "\033[35m", # Magenta
}

class _AnsiColoredFormatter(logging.Formatter):
  """
  Formatter that:
    - Wraps the level name in ANSI color codes
    - Emits timestamps with local timezone offset
    - Uses the pattern: LEVEL [logger.name] [YYYY-MM-DD HH:MM:SS±ZZZZ] message
  """
  _fmt = "%(levelname)s [%(name)s] [%(asctime)s] %(message)s"
  _datefmt = "%Y-%m-%d %H:%M:%S%z"

  def __init__(self):
    super().__init__(self._fmt, self._datefmt)

  def formatTime(self, record, datefmt=None):
    # create a timezone-aware datetime from the record
    dt = datetime.fromtimestamp(record.created).astimezone()
    return dt.strftime(datefmt or self._datefmt)

  def format(self, record):
    # inject color into record.levelname
    color = _LEVEL_COLORS.get(record.levelname, "")
    record.levelname = f"{color}{record.levelname}{_RESET}"
    return super().format(record)

def setup_logging(
  *,
  level: int = logging.INFO,
  stream=sys.stderr,
) -> None:
  """
  Configures the root logger with:
    - A single StreamHandler to `stream`
    - Our ANSI-colored, tz-aware formatter
    - The specified root level
  """
  handler = logging.StreamHandler(stream)
  handler.setFormatter(_AnsiColoredFormatter())

  # basicConfig will install our handler, set the level, and prevent
  # multiple handlers if called again.
  logging.basicConfig(level=level, handlers=[handler])

def get_logger(name: str) -> logging.Logger:
  return logging.getLogger(name)
