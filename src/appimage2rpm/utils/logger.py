#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logging utilities for the AppImage2RPM application.
"""

import os
import sys
import logging
import traceback
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from queue import Queue
from threading import Lock

from PySide6.QtCore import QObject, Signal, Slot


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