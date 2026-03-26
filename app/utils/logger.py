import logging
import logging.handlers

from config import Config


def get_logger(name: str = "bili") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))

    log_dir = "logs"
    handler = logging.handlers.RotatingFileHandler(
        f"{log_dir}/bili.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setLevel(logging.INFO)
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handler.setFormatter(logging.Formatter(format_str))

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(format_str))

    logger.addHandler(handler)
    logger.addHandler(console)

    return logger
