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


def _create_logger(
    name: str,
    *,
    level: int,
    propagate: bool,
    use_console: bool,
    log_file: Optional[Path],
    fmt: str,
    datefmt: Optional[str],
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = propagate

    if logger.handlers:
        return logger

    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

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


def create_app_logger(log_file: Path) -> logging.Logger:
    """Создаёт и настраивает основной логгер приложения."""
    return _create_logger(
        "doc2onto",
        level=logging.DEBUG,
        propagate=True,
        use_console=False,
        log_file=log_file,
        fmt="%(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def create_agents_logger(log_file: Path) -> logging.Logger:
    """Создаёт и настраивает отдельный логгер для запросов/ответов агентов."""
    return _create_logger(
        "doc2onto.agents",
        level=logging.INFO,
        propagate=False,
        use_console=False,
        log_file=log_file,
        fmt="%(message)s",
        datefmt=None,
    )
