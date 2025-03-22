#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logs widget for displaying application logs.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit,
    QComboBox, QLabel, QCheckBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat


class LogHandler(logging.Handler):
    """Custom logging handler that emits log messages as signals."""
    
    def __init__(self, callback) -> None:
        """
        Initialize the log handler.
        
        Args:
            callback: Function to call with log records
        """
        super().__init__()
        self.callback = callback
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.
        
        Args:
            record: The log record to emit
        """
        try:
            msg = self.format(record)
            self.callback(record, msg)
        except Exception:
            self.handleError(record)


class LogsWidget(QWidget):
    """
    Widget for displaying and filtering application logs.
    
    This widget shows log messages from the application and provides
    filtering options by log level.
    """
    
    def __init__(self) -> None:
        """Initialize the logs widget."""
        super().__init__()
        
        self.log_handler = LogHandler(self.handle_log)
        self.log_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            '%H:%M:%S'
        ))
        
        # Add the handler to the root logger
        logging.getLogger().addHandler(self.log_handler)
        
        self.log_colors = {
            logging.DEBUG: QColor(128, 128, 128),  # Gray
            logging.INFO: QColor(0, 0, 0),         # Black
            logging.WARNING: QColor(255, 165, 0),  # Orange
            logging.ERROR: QColor(255, 0, 0),      # Red
            logging.CRITICAL: QColor(139, 0, 0)    # Dark Red
        }
        
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Set up the user interface for the logs widget."""
        main_layout = QVBoxLayout(self)
        
        # Log level filter
        filter_layout = QHBoxLayout()
        
        self.level_label = QLabel("Log Level:")
        self.level_combo = QComboBox()
        self.level_combo.addItem("DEBUG", logging.DEBUG)
        self.level_combo.addItem("INFO", logging.INFO)
        self.level_combo.addItem("WARNING", logging.WARNING)
        self.level_combo.addItem("ERROR", logging.ERROR)
        self.level_combo.addItem("CRITICAL", logging.CRITICAL)
        self.level_combo.setCurrentIndex(1)  # Default to INFO
        self.level_combo.currentIndexChanged.connect(self.apply_log_filter)
        
        self.auto_scroll_check = QCheckBox("Auto Scroll")
        self.auto_scroll_check.setChecked(True)
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_logs)
        
        filter_layout.addWidget(self.level_label)
        filter_layout.addWidget(self.level_combo)
        filter_layout.addWidget(self.auto_scroll_check)
        filter_layout.addStretch()
        filter_layout.addWidget(self.clear_button)
        
        # Log text display
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setFont(QTextEdit.font(self.log_text))  # Monospace font
        
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.log_text)
        
        # Set minimum height
        self.setMinimumHeight(200)
    
    def handle_log(self, record: logging.LogRecord, formatted_msg: str) -> None:
        """
        Handle a log record by displaying it in the text widget.
        
        Args:
            record: The log record
            formatted_msg: The formatted log message
        """
        if record.levelno < self.level_combo.currentData():
            return
        
        # Add colored text
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        text_format = QTextCharFormat()
        text_format.setForeground(self.log_colors.get(record.levelno, QColor(0, 0, 0)))
        
        cursor.insertText(formatted_msg + "\n", text_format)
        
        # Auto scroll if enabled
        if self.auto_scroll_check.isChecked():
            self.log_text.setTextCursor(cursor)
            self.log_text.ensureCursorVisible()
    
    @Slot()
    def apply_log_filter(self) -> None:
        """Apply the selected log level filter."""
        self.clear_logs()
        
        # No need to reapply logs, new logs will be filtered automatically
        level = self.level_combo.currentData()
        logging.info(f"Log level filter set to {logging.getLevelName(level)}")
    
    @Slot()
    def clear_logs(self) -> None:
        """Clear all log messages from the display."""
        self.log_text.clear()
    
    def get_logs_text(self) -> str:
        """
        Get the current log text.
        
        Returns:
            The current log text as a string
        """
        return self.log_text.toPlainText()
    
    def closeEvent(self, event) -> None:
        """
        Handle the widget close event.
        
        Args:
            event: The close event
        """
        # Remove the log handler when the widget is closed
        logging.getLogger().removeHandler(self.log_handler)
        super().closeEvent(event) 