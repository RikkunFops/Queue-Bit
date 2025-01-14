from logging.config import dictConfig
import logging

# Custom formatter to remove non-UTF-8 characters
class UTF8SafeFormatter(logging.Formatter):
    def format(self, record):
        if record.msg:
            try:
                # Remove non-UTF-8 characters from the message
                record.msg = str(record.msg).encode("utf-8", errors="ignore").decode("utf-8")
            except Exception:
                record.msg = "Log message contained invalid characters and was sanitized."
        return super().format(record)

# Updated logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "()": UTF8SafeFormatter,  # Use the custom formatter
            "format": "%(levelname)-10s - %(asctime)s - %(module)-15s: %(message)s",
        },
        "standard": {
            "()": UTF8SafeFormatter,  # Use the custom formatter
            "format": "%(levelname)-10s - %(module)-15s: %(message)s",
        },
    },

    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "console_standard": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
        "file": {
            "level": "INFO",
            "class": "logging.FileHandler",
            "filename": "logs/error.log",
            "formatter": "verbose",
            "mode": "w",
        },
    },

    "loggers": {
        "discord": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "bot": {
            "handlers": ["console_standard", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Apply the configuration
dictConfig(LOGGING_CONFIG)

# Example usage
logger_standard = logging.getLogger("standard")
logger_error = logging.getLogger("error")
