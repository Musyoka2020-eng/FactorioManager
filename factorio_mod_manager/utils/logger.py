"""Logging utilities for Factorio Mod Manager."""
import logging
import sys
from pathlib import Path
from queue import Queue
from typing import Optional


class StreamRedirector:
    """Redirect stdout/stderr to logger."""

    def __init__(self, logger: logging.Logger, level: int = logging.INFO):
        """Initialize stream redirector.
        
        Args:
            logger: Logger to send output to
            level: Logging level for redirected output
        """
        self.logger = logger
        self.level = level

    def write(self, message: str) -> None:
        """Write message to logger."""
        if message and message.strip():
            self.logger.log(self.level, message.strip())

    def flush(self) -> None:
        """Flush operation (no-op)."""
        pass


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
    redirect_stdout: bool = True
) -> logging.Logger:
    """Set up a logger with console and optional UI handlers.
    
    Args:
        name: Logger name
        level: Logging level
        log_queue: Optional queue for UI logging
        redirect_stdout: Whether to redirect stdout/stderr to logger
        
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
    
    # UI handler (if queue provided)
    if log_queue:
        ui_handler = QueueHandler(log_queue)
        ui_handler.setLevel(level)
        ui_handler.setFormatter(formatter)
        logger.addHandler(ui_handler)
    
    # Redirect stdout/stderr to logger
    if redirect_stdout:
        sys.stdout = StreamRedirector(logger, logging.INFO)
        sys.stderr = StreamRedirector(logger, logging.ERROR)

    return logger

