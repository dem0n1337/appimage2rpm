#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converter widget module for the AppImage2RPM GUI.
"""

import os
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QFileDialog, QCheckBox,
    QComboBox, QSpinBox, QListWidget, QListWidgetItem, QProgressBar,
    QToolButton, QMessageBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QPixmap

from appimage2rpm.core.controller import AppImage2RPMController
from appimage2rpm.utils.file_utils import get_icon_preview


logger = logging.getLogger(__name__)


class ConverterWidget(QWidget):
    """
    Widget for converting AppImage to RPM.
    
    This widget provides the main interface for converting AppImage files
    to RPM packages, allowing users to select files, configure options,
    and monitor the conversion process.
    """
    
    # Signals
    conversion_started = Signal()
    conversion_finished = Signal(bool, str, str)
    progress_updated = Signal(int, str)
    
    def __init__(self, controller: AppImage2RPMController, parent: Optional[QWidget] = None) -> None:
        """
        Initialize the converter widget.
        
        Args:
            controller: The application controller
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.controller = controller
        self.appimage_path = ""
        self.output_dir = str(Path.home())
        self.conversion_thread = None
        self.icon_path = None
        
        # Set up the UI
        self.setup_ui()
        
        # Connect signals
        self.progress_updated.connect(self.update_progress)
        
    def setup_ui(self) -> None:
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)
        
        # Source group
        source_group = QGroupBox("Source")
        source_layout = QFormLayout(source_group)
        
        # AppImage path selection
        self.path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to AppImage file or directory")
        self.path_input.setReadOnly(True)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.browse_source)
        
        self.path_layout.addWidget(self.path_input)
        self.path_layout.addWidget(self.browse_button)
        
        source_layout.addRow("AppImage:", self.path_layout)
        
        # Use directory option
        self.use_directory = QCheckBox("Process a directory instead of an AppImage")
        self.use_directory.toggled.connect(self.toggle_source_type)
        source_layout.addRow("", self.use_directory)
        
        # Output directory
        self.output_layout = QHBoxLayout()
        self.output_input = QLineEdit(self.output_dir)
        self.output_input.setReadOnly(True)
        
        self.output_button = QPushButton("Browse...")
        self.output_button.clicked.connect(self.browse_output_dir)
        
        self.output_layout.addWidget(self.output_input)
        self.output_layout.addWidget(self.output_button)
        
        source_layout.addRow("Output:", self.output_layout)
        
        main_layout.addWidget(source_group)
        
        # Metadata group
        metadata_group = QGroupBox("Package Metadata")
        metadata_layout = QFormLayout(metadata_group)
        
        # Name
        self.name_input = QLineEdit()
        metadata_layout.addRow("Name:", self.name_input)
        
        # Version
        self.version_input = QLineEdit()
        metadata_layout.addRow("Version:", self.version_input)
        
        # Release
        self.release_input = QSpinBox()
        self.release_input.setMinimum(1)
        self.release_input.setValue(1)
        metadata_layout.addRow("Release:", self.release_input)
        
        # Summary
        self.summary_input = QLineEdit()
        metadata_layout.addRow("Summary:", self.summary_input)
        
        # Auto-dependencies
        self.auto_deps = QCheckBox("Automatically detect dependencies")
        self.auto_deps.setChecked(True)
        metadata_layout.addRow("", self.auto_deps)
        
        # Distribution profile
        self.profile_combo = QComboBox()
        self.load_distro_profiles()
        metadata_layout.addRow("Target Distribution:", self.profile_combo)
        
        # Icon selection
        icon_layout = QHBoxLayout()
        
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(48, 48)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.update_icon_preview(None)
        
        self.select_icon_button = QToolButton()
        self.select_icon_button.setText("...")
        self.select_icon_button.setToolTip("Select custom icon")
        self.select_icon_button.clicked.connect(self.select_icon)
        
        self.reset_icon_button = QToolButton()
        self.reset_icon_button.setText("×")
        self.reset_icon_button.setToolTip("Reset to default icon")
        self.reset_icon_button.clicked.connect(self.reset_icon)
        self.reset_icon_button.setEnabled(False)
        
        icon_layout.addWidget(self.icon_preview)
        icon_layout.addWidget(self.select_icon_button)
        icon_layout.addWidget(self.reset_icon_button)
        icon_layout.addStretch()
        
        metadata_layout.addRow("Icon:", icon_layout)
        
        main_layout.addWidget(metadata_group)
        
        # Conversion progress
        progress_group = QGroupBox("Conversion Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        
        main_layout.addWidget(progress_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.convert_button = QPushButton("Convert")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self.start_conversion)
        
        button_layout.addWidget(self.convert_button)
        
        main_layout.addLayout(button_layout)
        main_layout.addStretch()
        
    def load_distro_profiles(self) -> None:
        """Load available distribution profiles into the combo box."""
        self.profile_combo.clear()
        
        # Get profiles from controller
        profiles = self.controller.get_available_profiles()
        
        # Add profiles to combo box
        for profile in profiles:
            self.profile_combo.addItem(profile['name'], profile['id'])
            
        # Set current profile to detected distribution
        current_distro = self.controller.detect_current_distro()
        for i in range(self.profile_combo.count()):
            if self.profile_combo.itemData(i) == current_distro:
                self.profile_combo.setCurrentIndex(i)
                break
        
    def toggle_source_type(self) -> None:
        """Toggle between AppImage and directory source types."""
        is_directory = self.use_directory.isChecked()
        
        # Clear source path
        self.path_input.clear()
        self.appimage_path = ""
        
        # Update browse button behavior
        if is_directory:
            logger.debug("Switched to directory mode")
        else:
            logger.debug("Switched to AppImage mode")
            
        # Disable convert button until new source is selected
        self.convert_button.setEnabled(False)
        
    def browse_source(self) -> None:
        """Browse for AppImage file or directory."""
        if self.use_directory.isChecked():
            # Browse for directory
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Directory",
                str(Path.home())
            )
            
            if directory:
                self.appimage_path = directory
                self.path_input.setText(directory)
                self.convert_button.setEnabled(True)
                logger.info(f"Selected directory: {directory}")
        else:
            # Browse for AppImage file
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select AppImage file",
                str(Path.home()),
                "AppImage files (*.AppImage);;All files (*.*)"
            )
            
            if file_path:
                self.appimage_path = file_path
                self.path_input.setText(file_path)
                self.convert_button.setEnabled(True)
                logger.info(f"Selected AppImage: {file_path}")
                
    def browse_output_dir(self) -> None:
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            self.output_dir
        )
        
        if directory:
            self.output_dir = directory
            self.output_input.setText(directory)
            logger.info(f"Selected output directory: {directory}")
            
    def select_icon(self) -> None:
        """Select a custom icon file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Icon File",
            str(Path.home()),
            "Image files (*.png *.svg *.xpm);;All files (*.*)"
        )
        
        if file_path:
            self.icon_path = file_path
            self.update_icon_preview(file_path)
            self.reset_icon_button.setEnabled(True)
            logger.info(f"Selected custom icon: {file_path}")
            
    def reset_icon(self) -> None:
        """Reset to default icon."""
        self.icon_path = None
        self.update_icon_preview(None)
        self.reset_icon_button.setEnabled(False)
        logger.info("Reset to default icon")
        
    def update_icon_preview(self, icon_path: Optional[str]) -> None:
        """
        Update the icon preview.
        
        Args:
            icon_path: Path to the icon file
        """
        if icon_path and os.path.exists(icon_path):
            pixmap = get_icon_preview(icon_path, 48)
            if pixmap:
                self.icon_preview.setPixmap(pixmap)
                return
                
        # Default icon (no icon or failed to load)
        self.icon_preview.setText("No Icon")
        
    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata from form fields.
        
        Returns:
            Dict[str, Any]: Metadata dictionary
        """
        metadata = {}
        
        # Get values from form fields
        if self.name_input.text().strip():
            metadata['name'] = self.name_input.text().strip()
            
        if self.version_input.text().strip():
            metadata['version'] = self.version_input.text().strip()
            
        metadata['release'] = str(self.release_input.value())
        
        if self.summary_input.text().strip():
            metadata['summary'] = self.summary_input.text().strip()
            
        # Get selected distribution profile
        current_index = self.profile_combo.currentIndex()
        if current_index >= 0:
            metadata['distro_profile'] = self.profile_combo.itemData(current_index)
            
        # Include custom icon if selected
        if self.icon_path:
            metadata['icon_path'] = self.icon_path
            
        return metadata
    
    def set_appimage_path(self, path: str) -> None:
        """
        Set the AppImage path.
        
        Args:
            path: Path to the AppImage file
        """
        if not path:
            return
            
        self.appimage_path = path
        self.path_input.setText(path)
        self.convert_button.setEnabled(True)
        
        # Set use_directory checkbox based on whether path is a directory
        is_dir = os.path.isdir(path)
        self.use_directory.setChecked(is_dir)
        
    def start_conversion(self) -> None:
        """Start the conversion process."""
        if not self.appimage_path:
            QMessageBox.warning(
                self,
                "Missing Source",
                "Please select an AppImage file or directory first."
            )
            return
            
        # Disable controls during conversion
        self.disable_controls(True)
        
        # Reset progress
        self.progress_bar.setValue(0)
        self.status_label.setText("Starting conversion...")
        
        # Create metadata
        metadata = self.get_metadata()
        
        # Emit signal to indicate conversion started
        self.conversion_started.emit()
        
        # Start conversion thread
        self.conversion_thread = threading.Thread(
            target=self._run_conversion,
            args=(
                self.appimage_path,
                self.output_dir,
                metadata,
                self.profile_combo.itemData(self.profile_combo.currentIndex()),
                self.auto_deps.isChecked(),
                self.use_directory.isChecked()
            )
        )
        self.conversion_thread.daemon = True
        self.conversion_thread.start()
        
    def _run_conversion(
        self,
        appimage_path: str,
        output_dir: str,
        metadata: Dict[str, Any],
        distro_profile: str,
        auto_deps: bool,
        is_directory: bool
    ) -> None:
        """
        Run the conversion process in a separate thread.
        
        Args:
            appimage_path: Path to the AppImage file or directory
            output_dir: Output directory for the RPM package
            metadata: Package metadata
            distro_profile: Target distribution profile
            auto_deps: Whether to automatically detect dependencies
            is_directory: Whether appimage_path is a directory
        """
        try:
            # Start conversion with progress updates
            result = self.controller.convert_appimage(
                appimage_path=appimage_path,
                output_dir=output_dir,
                metadata=metadata,
                distro_profile=distro_profile,
                auto_deps=auto_deps,
                is_directory=is_directory,
                progress_callback=self._progress_callback
            )
            
            # Emit signal with result
            self.conversion_finished.emit(
                result["success"],
                result.get("rpm_path", ""),
                result.get("message", "Unknown error")
            )
            
        except Exception as e:
            logger.exception("Error during conversion")
            self.conversion_finished.emit(False, "", str(e))
            
    def _progress_callback(self, percent: int, message: str) -> None:
        """
        Callback for progress updates.
        
        Args:
            percent: Progress percentage (0-100)
            message: Progress message
        """
        self.progress_updated.emit(percent, message)
        
    @Slot(int, str)
    def update_progress(self, value: int, message: str) -> None:
        """
        Update the progress bar and status label.
        
        Args:
            value: Progress value (0-100)
            message: Progress message
        """
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        
    def disable_controls(self, disabled: bool) -> None:
        """
        Enable or disable controls during conversion.
        
        Args:
            disabled: Whether to disable the controls
        """
        self.browse_button.setEnabled(not disabled)
        self.output_button.setEnabled(not disabled)
        self.convert_button.setEnabled(not disabled)
        self.use_directory.setEnabled(not disabled)
        self.name_input.setEnabled(not disabled)
        self.version_input.setEnabled(not disabled)
        self.release_input.setEnabled(not disabled)
        self.summary_input.setEnabled(not disabled)
        self.auto_deps.setEnabled(not disabled)
        self.profile_combo.setEnabled(not disabled)
        self.select_icon_button.setEnabled(not disabled)
        self.reset_icon_button.setEnabled(not disabled and self.icon_path is not None) 