import logging
from pathlib import Path
from typing import Optional

"""
Принятые уровни логирования:
1. DEBUG — диагностическая информация
2. INFO — контрольные точки работы системы
3. WARNING — некритические ошибоки, приостановка пайплайна
4. ERROR — критические ошибоки, падения модулей, невозможность продолжения работы
5. CRITICAL — сервис в нерабочем состоянии, риск потери данных/безопасности
"""


def create_logger(use_console: bool = True, log_file: Optional[Path] = None) -> logging.Logger:
    """Создаёт и настраивает логгер для приложения."""
    logger = logging.getLogger("doc2onto")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
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
