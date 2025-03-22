#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logging utilities for AppImage2RPM.
"""

import os
import sys
import logging
import traceback
import time
from pathlib import Path
from typing import Optional, Dict, Any, Union
from queue import Queue
from threading import Lock

from PySide6.QtCore import QObject, Signal, Slot

# Define log levels and their names
LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# Default log format
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Application log directory
def get_log_dir() -> Path:
    """
    Get the directory for storing application logs.
    
    Returns:
        Path to the log directory
    """
    if sys.platform == "win32":
        log_dir = Path(os.path.expandvars("%APPDATA%")) / "AppImage2RPM" / "logs"
    else:
        log_dir = Path.home() / ".config" / "appimage2rpm" / "logs"
        
    os.makedirs(log_dir, exist_ok=True)
    return log_dir

def configure_logging(
    level: Union[str, int] = "info",
    log_file: Optional[str] = None,
    console: bool = True,
    log_format: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT
) -> None:
    """
    Configure the logging system for the application.
    
    Args:
        level: Log level (debug, info, warning, error, critical) or logging level constant
        log_file: Optional path to log file
        console: Whether to log to console
        log_format: Format string for log messages
        date_format: Format string for date/time in log messages
    """
    # Convert string level to logging constant if needed
    if isinstance(level, str):
        level = level.lower()
        level = LOG_LEVELS.get(level, logging.INFO)
    
    # Create root logger and set level
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(log_format, date_format)
    
    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Failed to create log file handler: {str(e)}")
    
    # Add a default log file in the user's config directory
    if not log_file:
        try:
            log_dir = get_log_dir()
            default_log_file = log_dir / "appimage2rpm.log"
            file_handler = logging.FileHandler(str(default_log_file))
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Failed to create default log file handler: {str(e)}")
    
    # Add a handler that logs warnings and above to stderr
    class StdErrHandler(logging.StreamHandler):
        """Handler for logging warnings and above to stderr."""
        def __init__(self):
            super().__init__(sys.stderr)
            self.setLevel(logging.WARNING)
    
    stderr_handler = StdErrHandler()
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)
    
    # Log that the logging system is initialized
    logging.info("Logging system initialized")


class LogCapture:
    """
    Utility class to capture logs during a specific operation.
    
    This class helps collect logs during an operation that can be
    later retrieved for display or analysis.
    """
    
    def __init__(self, log_format: str = DEFAULT_LOG_FORMAT) -> None:
        """
        Initialize the log capture.
        
        Args:
            log_format: Format string for log messages
        """
        self.log_format = log_format
        self.formatter = logging.Formatter(log_format)
        self.logs = []
        self.handler = self._create_handler()
    
    def _create_handler(self) -> logging.Handler:
        """
        Create a handler that captures logs.
        
        Returns:
            A logging handler that stores logs in memory
        """
        class CaptureHandler(logging.Handler):
            def __init__(self, callback):
                super().__init__()
                self.callback = callback
            
            def emit(self, record):
                formatted = self.format(record)
                self.callback(record, formatted)
        
        handler = CaptureHandler(self._handle_log)
        handler.setFormatter(self.formatter)
        return handler
    
    def _handle_log(self, record: logging.LogRecord, formatted: str) -> None:
        """
        Handle a log record.
        
        Args:
            record: The log record
            formatted: The formatted log message
        """
        self.logs.append((record, formatted))
    
    def start(self) -> None:
        """Start capturing logs."""
        logging.getLogger().addHandler(self.handler)
    
    def stop(self) -> None:
        """Stop capturing logs."""
        logging.getLogger().removeHandler(self.handler)
    
    def get_logs(self) -> list:
        """
        Get the captured logs.
        
        Returns:
            List of captured log records and their formatted messages
        """
        return self.logs
    
    def get_formatted_logs(self) -> str:
        """
        Get captured logs as a formatted string.
        
        Returns:
            String containing all captured logs
        """
        return "\n".join(formatted for _, formatted in self.logs)
    
    def clear(self) -> None:
        """Clear the captured logs."""
        self.logs = []
    
    def __enter__(self):
        """Start capturing when used as a context manager."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop capturing when exiting the context manager."""
        self.stop()
        return False  # Don't suppress exceptions


class LogHandler(QObject, logging.Handler):
    """
    Custom log handler that emits Qt signals for log messages.
    
    This handler bridges Python's logging system with Qt's signal/slot mechanism
    to enable showing logs in the GUI while also supporting terminal output.
    """
    
    # Signal emitted when a new log message arrives
    log_signal = Signal(int, str)
    
    def __init__(self) -> None:
        """Initialize the log handler."""
        QObject.__init__(self)
        logging.Handler.__init__(self)
        
        # Format for log messages
        self.setFormatter(logging.Formatter('%(message)s'))
        
        # Queue for log messages (thread-safe)
        self.log_queue = Queue()
        self.lock = Lock()
        
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.
        
        This method is called by the logging system when a new log message
        is generated. It formats the message and emits a Qt signal.
        
        Args:
            record: Log record object
        """
        # Format the log message
        msg = self.format(record)
        
        # Store formatted record in queue (thread-safe)
        with self.lock:
            self.log_queue.put((record.levelno, msg))
            
        # Emit signal
        self.log_signal.emit(record.levelno, msg)
        
    def process_logs(self) -> None:
        """Process all pending logs in the queue."""
        with self.lock:
            while not self.log_queue.empty():
                level, msg = self.log_queue.get()
                self.log_signal.emit(level, msg)


class StreamToLogger:
    """
    Stream-like object that redirects writes to a logger.
    
    This class can be used to redirect stdout/stderr to the logging system.
    """
    
    def __init__(self, logger: logging.Logger, level: int = logging.INFO) -> None:
        """
        Initialize the stream to logger object.
        
        Args:
            logger: Logger to write messages to
            level: Log level to use
        """
        self.logger = logger
        self.level = level
        self.buffer = ""
        
    def write(self, message: str) -> None:
        """
        Write a message to the logger.
        
        Args:
            message: Message to write
        """
        # If the message ends with a newline, log it
        if message and message.strip():
            self.buffer += message
            if self.buffer.endswith('\n'):
                self.logger.log(self.level, self.buffer.rstrip())
                self.buffer = ""
                
    def flush(self) -> None:
        """Flush the buffer to the logger."""
        if self.buffer:
            self.logger.log(self.level, self.buffer)
            self.buffer = ""


def configure_logging(log_to_file: bool = False, log_dir: Optional[str] = None) -> None:
    """
    Configure application logging.
    
    This function sets up logging to console and optionally to file,
    and redirects stdout/stderr to the logging system.
    
    Args:
        log_to_file: Whether to log to a file
        log_dir: Directory to store log files
    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    root_logger.addHandler(console_handler)
    
    # Configure file handler if requested
    if log_to_file:
        try:
            # Create log directory if needed
            if log_dir:
                log_path = Path(log_dir)
            else:
                log_path = Path.home() / ".appimage2rpm" / "logs"
                
            os.makedirs(log_path, exist_ok=True)
            
            # Create timestamped log file
            log_file = log_path / f"appimage2rpm_{time.strftime('%Y%m%d_%H%M%S')}.log"
            
            # Add file handler
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            root_logger.addHandler(file_handler)
            
            logging.info(f"Logging to file: {log_file}")
            
        except Exception as e:
            logging.error(f"Failed to set up file logging: {str(e)}")
    
    # Redirect stdout and stderr to logger
    stdout_logger = logging.getLogger("STDOUT")
    stderr_logger = logging.getLogger("STDERR")
    
    sys.stdout = StreamToLogger(stdout_logger, logging.INFO)
    sys.stderr = StreamToLogger(stderr_logger, logging.ERROR)
    
    # Log uncaught exceptions
    def exception_handler(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions by logging them."""
        if issubclass(exc_type, KeyboardInterrupt):
            # Call the default handler for KeyboardInterrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
            
        # Log the exception
        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        
    # Set the exception handler
    sys.excepthook = exception_handler
    
    logging.info("Logging system initialized") 