import os
import logging
import colorlog
from google.cloud.logging import Client
from google.cloud.logging.handlers import StructuredLogHandler


def setup_app_logger(logger_name: str, console_level: int = logging.INFO):
    """
    Sets up a centralized application logger with colored console output
    and integration with Google Cloud Logging via StructuredLogHandler.
    """

    app_logger_name = f"local_{logger_name}"

    os.environ["DEFAULT_LOGGER_NAME"] = app_logger_name

    local_logger = logging.getLogger(app_logger_name)
    local_logger.setLevel(logging.DEBUG)

    if not local_logger.handlers:
        # 1. Console Handler with Colors
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)

        log_colors = {
            'DEBUG':    'cyan',
            'INFO':     'green',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'red,bg_white',
        }

        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(levelname)-8s%(reset)s: %(asctime)s - %(blue)s%(name)s%(reset)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors=log_colors
        )
        console_handler.setFormatter(console_formatter)
        local_logger.addHandler(console_handler)

