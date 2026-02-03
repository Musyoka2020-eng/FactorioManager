"""Logging utilities for Factorio Mod Manager."""
import logging
import sys
from pathlib import Path
from queue import Queue
from typing import Optional


class QueueHandler(logging.Handler):
    """Handler that puts log records into a queue for UI consumption."""

    def __init__(self, log_queue: Queue):
        """Initialize queue handler."""
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        """Put log record into queue."""
        try:
            self.log_queue.put(self.format(record))
        except Exception:
            self.handleError(record)


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_queue: Optional[Queue] = None,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """Set up a logger with console, file, and optional UI handlers.
    
    Args:
        name: Logger name
        level: Logging level
        log_queue: Optional queue for UI logging
        log_file: Optional file path for file logging
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    
    # Add handler if not already present
    if not logger.handlers:
        logger.addHandler(console_handler)
    
    # File handler (if log_file provided)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not set up file logging to {log_file}: {e}")
    
    # UI handler (if queue provided)
    if log_queue:
        ui_handler = QueueHandler(log_queue)
        ui_handler.setLevel(level)
        ui_handler.setFormatter(formatter)
        logger.addHandler(ui_handler)

    return logger



