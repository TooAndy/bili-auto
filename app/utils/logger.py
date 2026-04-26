import logging
import logging.handlers
import os

from config import Config


def get_logger(name: str = "bili") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    # 按天轮转，保留30天
    handler = logging.handlers.TimedRotatingFileHandler(
        when="midnight",
        interval=1,
        backupCount=30,
        filename=f"{log_dir}/bili.log",
        encoding="utf-8",
    )
    # 轮转后在新文件名前加日期后缀
    handler.suffix = "%Y-%m-%d.log"
    handler.setLevel(log_level)
    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handler.setFormatter(logging.Formatter(format_str))

    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(format_str))

    logger.addHandler(handler)
    logger.addHandler(console)

    return logger
