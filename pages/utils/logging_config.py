import logging
import os
import sys
from datetime import datetime

LOG_DIR = "logs"
LOG_NAME = "stock_dashboard"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"


class SafeStreamHandler(logging.StreamHandler):
    """StreamHandler that never raises on characters the console cannot encode.

    Windows consoles default to cp1252, so logging a rupee sign or an emoji
    would otherwise raise UnicodeEncodeError and take the page down.

    emit() is fully reimplemented because StreamHandler.emit swallows encoding
    errors itself and routes them to handleError, so wrapping a super() call
    would never see the failure.
    """

    def emit(self, record):
        try:
            message = self.format(record)
        except Exception:
            self.handleError(record)
            return

        try:
            stream = self.stream
            stream.write(message + self.terminator)
            self.flush()
            return
        except UnicodeEncodeError:
            pass
        except Exception:
            self.handleError(record)
            return

        # retry with characters the console cannot represent replaced
        try:
            encoding = getattr(self.stream, "encoding", None) or "ascii"
            safe = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
            self.stream.write(safe + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def _build_file_handler(log_filename: str):
    """Return a UTF-8 file handler, or None when the file cannot be opened."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        return logging.FileHandler(log_filename, encoding="utf-8")
    except OSError:
        return None


def setup_logger(name: str = __name__, level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application logger.

    Safe to call from every page: the handlers are attached only once, so a
    Streamlit rerun or a second page cannot duplicate log output.
    """
    logger = logging.getLogger(name)

    if getattr(logger, "_stock_dashboard_configured", False):
        return logger

    logger.setLevel(level)

    # let records reach this logger without being handled twice by the root
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT)

    log_filename = os.path.join(
        LOG_DIR, f"{LOG_NAME}_{datetime.now().strftime('%Y%m%d')}.log"
    )

    handlers = [h for h in [_build_file_handler(log_filename), SafeStreamHandler(sys.stdout)] if h]

    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    if not any(isinstance(h, logging.FileHandler) for h in handlers):
        logger.warning("Log file unavailable, logging to console only")

    logger._stock_dashboard_configured = True

    return logger