#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logs widget module for the AppImage2RPM GUI.
"""

import os
import logging
import time
from typing import Optional, Dict, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QComboBox, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtGui import QColor, QTextCharFormat, QBrush, QTextCursor

from appimage2rpm.utils.logger import LogHandler


class ColoredTextEdit(QPlainTextEdit):
    """
    Text edit widget with support for colored log messages.
    
    This widget extends QPlainTextEdit to provide color-coded log messages
    based on severity level.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the colored text edit.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Make the text edit read-only
        self.setReadOnly(True)
        
        # Set up font
        font = self.font()
        font.setFamily("Monospace")
        font.setFixedPitch(True)
        self.setFont(font)
        
        # Define colors for different log levels
        self.log_colors = {
            logging.DEBUG: QColor(128, 128, 128),     # Gray
            logging.INFO: QColor(0, 0, 0),            # Black
            logging.WARNING: QColor(255, 165, 0),     # Orange
            logging.ERROR: QColor(255, 0, 0),         # Red
            logging.CRITICAL: QColor(255, 0, 0, 255), # Bright red
        }
        
    def append_log(self, msg: str, level: int = logging.INFO) -> None:
        """
        Append a log message with appropriate color.
        
        Args:
            msg: Log message
            level: Log level
        """
        # Get color for log level
        color = self.log_colors.get(level, QColor(0, 0, 0))
        
        # Create text format with color
        format = QTextCharFormat()
        format.setForeground(QBrush(color))
        
        # Add text with color
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(msg + '\n', format)
        
        # Scroll to bottom
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


class LogsWidget(QWidget):
    """
    Widget for displaying application logs.
    
    This widget shows a scrollable log view with color-coded messages
    and provides controls for filtering and saving logs.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the logs widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store logs for filtering
        self.logs = []
        
        # Set up the UI
        self.setup_ui()
        
        # Register log handler
        self.log_handler = LogHandler()
        self.log_handler.log_signal.connect(self.on_log_message)
        
        # Get root logger and add handler
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        
        # Update logs periodically
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_pending_logs)
        self.timer.start(100)  # Update every 100ms
        
    def setup_ui(self) -> None:
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Controls layout
        controls_layout = QHBoxLayout()
        
        # Log level filter
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("Debug", logging.DEBUG)
        self.filter_combo.addItem("Info", logging.INFO)
        self.filter_combo.addItem("Warning", logging.WARNING)
        self.filter_combo.addItem("Error", logging.ERROR)
        self.filter_combo.addItem("Critical", logging.CRITICAL)
        self.filter_combo.setCurrentIndex(1)  # Default to INFO
        self.filter_combo.currentIndexChanged.connect(self.apply_filter)
        
        # Label for filter
        filter_label = QLabel("Log Level:")
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_logs)
        
        controls_layout.addWidget(filter_label)
        controls_layout.addWidget(self.filter_combo)
        controls_layout.addStretch()
        controls_layout.addWidget(self.clear_button)
        
        # Log text display
        self.log_display = ColoredTextEdit()
        
        # Add widgets to layout
        layout.addLayout(controls_layout)
        layout.addWidget(self.log_display)
        
    def clear_logs(self) -> None:
        """Clear the log display."""
        self.log_display.clear()
        self.logs = []
        
    def save_logs(self, file_path: str) -> None:
        """
        Save logs to a file.
        
        Args:
            file_path: Path to save the logs
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.log_display.toPlainText())
        except Exception as e:
            logging.error(f"Error saving logs: {str(e)}")
            
    @Slot(int, str)
    def on_log_message(self, level: int, message: str) -> None:
        """
        Handle new log message.
        
        Args:
            level: Log level
            message: Log message
        """
        # Store log for filtering
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append((timestamp, level, message))
        
        # Apply filter
        current_filter = self.filter_combo.currentData()
        if level >= current_filter:
            self.log_display.append_log(f"{timestamp} - {message}", level)
            
    def apply_filter(self) -> None:
        """Apply the selected log level filter."""
        # Get selected filter level
        filter_level = self.filter_combo.currentData()
        
        # Clear and re-add filtered logs
        self.log_display.clear()
        for timestamp, level, message in self.logs:
            if level >= filter_level:
                self.log_display.append_log(f"{timestamp} - {message}", level)
                
    def process_pending_logs(self) -> None:
        """Process any pending log messages."""
        # This method is called periodically by the timer
        # LogHandler already handles buffering and emits signals
        # for each log message, so nothing else is needed here
        pass 