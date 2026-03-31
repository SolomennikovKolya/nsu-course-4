import logging
from pathlib import Path
from typing import Optional


def create_logger(use_console: bool = True, log_file: Optional[Path] = None) -> logging.Logger:
    """Создаёт и настраивает логгер для приложения."""
    logger = logging.getLogger("doc2onto")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        # fmt="%(asctime)s | %(levelname)-7s | %(message)s",
        fmt="%(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if use_console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
