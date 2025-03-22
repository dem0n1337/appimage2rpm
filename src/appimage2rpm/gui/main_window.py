#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main window module for the AppImage2RPM GUI.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFileDialog, QMessageBox, QSizePolicy,
    QApplication, QTabWidget, QProgressBar
)
from PySide6.QtCore import Qt, QSize, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap, QAction

from appimage2rpm.gui.converter_widget import ConverterWidget
from appimage2rpm.gui.logs_widget import LogsWidget
from appimage2rpm.gui.profile_widget import DistroProfileWidget
from appimage2rpm.gui.repo_widget import RepoManagerWidget
from appimage2rpm.gui.about_dialog import AboutDialog
from appimage2rpm.core.controller import AppImage2RPMController
from appimage2rpm.utils.logger import configure_logging


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """
    Main window for the AppImage2RPM application.
    
    This class creates the main application window and manages its components.
    """
    
    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        
        # Configure logging
        configure_logging()
        
        # Initialize the controller
        self.controller = AppImage2RPMController()
        
        # Set up the UI
        self.setup_ui()
        
    def setup_ui(self) -> None:
        """Set up the user interface."""
        # Set window properties
        self.setWindowTitle("AppImage2RPM Converter")
        self.setMinimumSize(800, 600)
        
        # Create main widget and layout
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create tab widget for main functionality
        tab_widget = QTabWidget()
        
        # Converter tab
        self.converter_widget = ConverterWidget(self.controller)
        self.converter_widget.conversion_started.connect(self.on_conversion_started)
        self.converter_widget.conversion_finished.connect(self.on_conversion_finished)
        tab_widget.addTab(self.converter_widget, "Converter")
        
        # Profile manager tab
        self.profile_widget = DistroProfileWidget(self.controller)
        tab_widget.addTab(self.profile_widget, "Distribution Profiles")
        
        # Repository manager tab
        self.repo_widget = RepoManagerWidget(self.controller)
        tab_widget.addTab(self.repo_widget, "Repository Manager")
        
        # Create splitter to divide tabs and logs
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(tab_widget)
        
        # Log area
        self.logs_widget = LogsWidget()
        splitter.addWidget(self.logs_widget)
        
        # Set initial splitter sizes (70% for tabs, 30% for logs)
        splitter.setSizes([700, 300])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        
        # Add status bar
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Set central widget
        self.setCentralWidget(central_widget)
        
        # Center window on screen
        self.center_on_screen()
        
        logger.info("Main window UI initialized")
        
    def create_menu_bar(self) -> None:
        """Create the menu bar."""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        
        # Open AppImage
        open_action = QAction("&Open AppImage...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_appimage)
        file_menu.addAction(open_action)
        
        # Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Tools menu
        tools_menu = menu_bar.addMenu("&Tools")
        
        # Clear logs
        clear_logs_action = QAction("&Clear Logs", self)
        clear_logs_action.triggered.connect(self.logs_widget.clear_logs)
        tools_menu.addAction(clear_logs_action)
        
        # Save logs
        save_logs_action = QAction("&Save Logs...", self)
        save_logs_action.triggered.connect(self.save_logs)
        tools_menu.addAction(save_logs_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        
        # About
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def center_on_screen(self) -> None:
        """Center the window on the screen."""
        # Get the screen size
        screen = QApplication.primaryScreen().size()
        
        # Calculate the center position
        size = self.size()
        x = (screen.width() - size.width()) // 2
        y = (screen.height() - size.height()) // 2
        
        # Move the window
        self.move(x, y)
        
    def open_appimage(self) -> None:
        """Open an AppImage file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open AppImage file",
            str(Path.home()),
            "AppImage files (*.AppImage);;All files (*.*)"
        )
        
        if file_path:
            logger.info(f"Selected AppImage: {file_path}")
            self.converter_widget.set_appimage_path(file_path)
            
    def save_logs(self) -> None:
        """Save logs to a file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            str(Path.home() / "appimage2rpm.log"),
            "Log files (*.log);;Text files (*.txt);;All files (*.*)"
        )
        
        if file_path:
            logger.info(f"Saving logs to: {file_path}")
            self.logs_widget.save_logs(file_path)
            
    def show_about(self) -> None:
        """Show the about dialog."""
        about_dialog = AboutDialog(self)
        about_dialog.exec()
        
    @Slot()
    def on_conversion_started(self) -> None:
        """Handle conversion started event."""
        logger.info("Conversion started")
        self.progress_bar.setVisible(True)
        self.status_bar.showMessage("Converting AppImage...")
        
    @Slot(bool, str, str)
    def on_conversion_finished(self, success: bool, rpm_path: str, message: str) -> None:
        """
        Handle conversion finished event.
        
        Args:
            success: Whether the conversion was successful
            rpm_path: Path to the generated RPM file
            message: Success or error message
        """
        self.progress_bar.setVisible(False)
        
        if success:
            logger.info(f"Conversion succeeded: {rpm_path}")
            self.status_bar.showMessage(f"Conversion complete: {message}", 5000)
        else:
            logger.error(f"Conversion failed: {message}")
            self.status_bar.showMessage(f"Conversion failed: {message}", 5000)
            
    def closeEvent(self, event) -> None:
        """
        Handle window close event.
        
        Args:
            event: Close event
        """
        logger.info("Application shutdown")
        event.accept() 