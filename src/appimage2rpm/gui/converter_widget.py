#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Converter widget for the AppImage2RPM GUI.
"""

import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple, Union

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QFormLayout, QGroupBox, QFileDialog, QMessageBox,
    QCheckBox, QComboBox, QProgressBar, QSplitter, QTabWidget,
    QTextEdit, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QSize
from PySide6.QtGui import QIcon

from appimage2rpm.core.controller import AppImage2RPMController


logger = logging.getLogger(__name__)


class ConversionThread(QThread):
    """
    Thread for handling AppImage conversion in the background.
    
    This thread runs the conversion process without blocking the GUI.
    """
    
    # Signals for progress updates and completion
    progress_update = Signal(int, str)
    conversion_finished = Signal(bool, str, str)  # success, rpm_path, message
    
    def __init__(
        self,
        controller: AppImage2RPMController,
        appimage_path: str,
        output_dir: str,
        metadata: Dict[str, Any],
        distro_profile: Optional[str] = None,
        auto_deps: bool = True,
        is_directory: bool = False
    ) -> None:
        """
        Initialize the conversion thread.
        
        Args:
            controller: AppImage2RPMController instance
            appimage_path: Path to the AppImage file
            output_dir: Directory for output
            metadata: Package metadata
            distro_profile: Optional distribution profile ID
            auto_deps: Whether to automatically analyze dependencies
            is_directory: Whether the input is a directory instead of an AppImage
        """
        super().__init__()
        
        self.controller = controller
        self.appimage_path = appimage_path
        self.output_dir = output_dir
        self.metadata = metadata
        self.distro_profile = distro_profile
        self.auto_deps = auto_deps
        self.is_directory = is_directory
    
    def progress_callback(self, percent: int, message: str) -> None:
        """
        Callback for progress updates from the controller.
        
        Args:
            percent: Percentage of completion (0-100)
            message: Progress message
        """
        self.progress_update.emit(percent, message)
    
    def run(self) -> None:
        """Run the conversion process."""
        try:
            logger.info(f"Starting conversion of {self.appimage_path}")
            
            result = self.controller.convert_appimage(
                appimage_path=self.appimage_path,
                output_dir=self.output_dir,
                metadata=self.metadata,
                distro_profile=self.distro_profile,
                auto_deps=self.auto_deps,
                progress_callback=self.progress_callback,
                is_directory=self.is_directory
            )
            
            if result and "rpm_path" in result:
                rpm_path = result["rpm_path"]
                logger.info(f"Conversion completed successfully: {rpm_path}")
                self.conversion_finished.emit(True, rpm_path, "Conversion completed successfully")
            else:
                logger.error("Conversion failed")
                self.conversion_finished.emit(False, "", "Conversion failed")
                
        except Exception as e:
            logger.exception("Error during conversion")
            self.conversion_finished.emit(False, "", f"Error: {str(e)}")


class ConverterWidget(QWidget):
    """
    Widget for converting AppImage files to RPM.
    
    This widget provides a user interface for selecting an AppImage,
    configuring the conversion settings, and initiating the conversion.
    """
    
    conversion_started = Signal()
    conversion_finished = Signal(bool, str, str)  # success, rpm_path, message
    
    def __init__(self, controller: Optional[AppImage2RPMController] = None) -> None:
        """
        Initialize the converter widget.
        
        Args:
            controller: Optional AppImage2RPMController instance
        """
        super().__init__()
        
        self.controller = controller or AppImage2RPMController()
        self.conversion_thread = None
        self.is_directory_mode = False
        
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Set up the user interface for the converter widget."""
        main_layout = QVBoxLayout(self)
        
        # File selection
        file_group = QGroupBox("AppImage Selection")
        file_layout = QVBoxLayout(file_group)
        
        file_input_layout = QHBoxLayout()
        self.file_label = QLabel("AppImage File:")
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_button = QPushButton("Browse...")
        self.file_button.clicked.connect(self.browse_appimage)
        
        self.dir_mode_check = QCheckBox("Directory Mode")
        self.dir_mode_check.setToolTip("Convert a directory instead of an AppImage file")
        self.dir_mode_check.toggled.connect(self.toggle_directory_mode)
        
        file_input_layout.addWidget(self.file_label)
        file_input_layout.addWidget(self.file_edit)
        file_input_layout.addWidget(self.file_button)
        
        file_layout.addLayout(file_input_layout)
        file_layout.addWidget(self.dir_mode_check)
        
        # Output directory
        output_layout = QHBoxLayout()
        output_label = QLabel("Output Directory:")
        self.output_edit = QLineEdit()
        self.output_edit.setReadOnly(True)
        self.output_button = QPushButton("Browse...")
        self.output_button.clicked.connect(self.browse_output_dir)
        
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_button)
        
        file_layout.addLayout(output_layout)
        
        # Package metadata
        metadata_group = QGroupBox("Package Metadata")
        metadata_layout = QFormLayout(metadata_group)
        
        self.name_edit = QLineEdit()
        self.version_edit = QLineEdit()
        self.release_edit = QLineEdit("1")
        self.summary_edit = QLineEdit()
        self.license_edit = QLineEdit("Unspecified")
        
        metadata_layout.addRow("Name:", self.name_edit)
        metadata_layout.addRow("Version:", self.version_edit)
        metadata_layout.addRow("Release:", self.release_edit)
        metadata_layout.addRow("Summary:", self.summary_edit)
        metadata_layout.addRow("License:", self.license_edit)
        
        # Advanced options
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QFormLayout(advanced_group)
        
        self.distro_combo = QComboBox()
        self.auto_deps_check = QCheckBox("Automatically analyze dependencies")
        self.auto_deps_check.setChecked(True)
        
        advanced_layout.addRow("Distribution:", self.distro_combo)
        advanced_layout.addRow("", self.auto_deps_check)
        
        # Progress bar
        progress_group = QGroupBox("Conversion Progress")
        progress_layout = QVBoxLayout(progress_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        self.progress_label = QLabel("Ready")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)
        self.convert_button.setEnabled(False)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.cancel_button.setEnabled(False)
        
        button_layout.addStretch()
        button_layout.addWidget(self.convert_button)
        button_layout.addWidget(self.cancel_button)
        
        # Add everything to main layout
        main_layout.addWidget(file_group)
        main_layout.addWidget(metadata_group)
        main_layout.addWidget(advanced_group)
        main_layout.addWidget(progress_group)
        main_layout.addLayout(button_layout)
        
        # Load distribution profiles
        self.load_distro_profiles()
    
    def load_distro_profiles(self) -> None:
        """Load available distribution profiles."""
        self.distro_combo.clear()
        
        # Add "Auto-detect" option
        self.distro_combo.addItem("Auto-detect", None)
        
        # Get available profiles
        profiles = self.controller.get_available_profiles()
        
        for profile in profiles:
            name = profile.get("name", "Unknown")
            version = profile.get("version", "")
            if version:
                display_name = f"{name} {version}"
            else:
                display_name = name
                
            self.distro_combo.addItem(display_name, profile.get("id"))
        
        # Try to detect current distro
        current_distro = self.controller.detect_current_distro()
        if current_distro:
            for i in range(self.distro_combo.count()):
                if self.distro_combo.itemData(i) == current_distro:
                    self.distro_combo.setCurrentIndex(i)
                    break
    
    def browse_appimage(self) -> None:
        """Browse for an AppImage file or directory."""
        if self.is_directory_mode:
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Directory to Convert",
                str(Path.home())
            )
            
            if directory:
                self.file_edit.setText(directory)
                self.file_path_changed()
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select AppImage File",
                str(Path.home()),
                "AppImage Files (*.AppImage *.appimage);;All Files (*)"
            )
            
            if file_path:
                self.file_edit.setText(file_path)
                self.file_path_changed()
    
    def browse_output_dir(self) -> None:
        """Browse for output directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(Path.home())
        )
        
        if directory:
            self.output_edit.setText(directory)
    
    def toggle_directory_mode(self, checked: bool) -> None:
        """
        Toggle between AppImage and directory mode.
        
        Args:
            checked: Whether directory mode is enabled
        """
        self.is_directory_mode = checked
        
        if checked:
            self.file_label.setText("Directory:")
            self.file_button.setText("Browse Directory...")
            self.file_edit.clear()
        else:
            self.file_label.setText("AppImage File:")
            self.file_button.setText("Browse...")
            self.file_edit.clear()
    
    def file_path_changed(self) -> None:
        """Handle changes to the file path."""
        file_path = self.file_edit.text()
        
        if not file_path:
            self.convert_button.setEnabled(False)
            return
        
        # Enable convert button
        self.convert_button.setEnabled(True)
        
        # Set default output directory if not set
        if not self.output_edit.text():
            parent_dir = str(Path(file_path).parent)
            self.output_edit.setText(parent_dir)
        
        # Try to extract name and version from AppImage filename
        if not self.is_directory_mode:
            filename = Path(file_path).stem
            # Common pattern: AppName-vX.Y.Z-arch.AppImage
            parts = filename.split('-')
            
            if len(parts) >= 2:
                # Guess app name (everything before last two segments)
                app_name = '-'.join(parts[:-2]) if len(parts) > 2 else parts[0]
                
                # Guess version (segment that starts with 'v' or contains dots)
                version_part = None
                for part in parts[1:]:
                    if part.startswith('v') or '.' in part:
                        version_part = part
                        break
                
                if app_name and not self.name_edit.text():
                    self.name_edit.setText(app_name.lower())
                
                if version_part and not self.version_edit.text():
                    # Remove 'v' prefix if present
                    if version_part.startswith('v'):
                        version_part = version_part[1:]
                    self.version_edit.setText(version_part)
        else:
            # For directory mode, use directory name as package name
            dir_name = Path(file_path).name
            if dir_name and not self.name_edit.text():
                self.name_edit.setText(dir_name.lower())
    
    def validate_inputs(self) -> Optional[str]:
        """
        Validate user inputs before starting conversion.
        
        Returns:
            Error message if validation fails, None otherwise
        """
        file_path = self.file_edit.text()
        output_dir = self.output_edit.text()
        name = self.name_edit.text()
        version = self.version_edit.text()
        
        if not file_path:
            return "Please select an AppImage file or directory"
        
        if not Path(file_path).exists():
            return "Selected file or directory does not exist"
        
        if not output_dir:
            return "Please select an output directory"
        
        if not Path(output_dir).exists():
            return "Output directory does not exist"
        
        if not name:
            return "Package name is required"
        
        if not version:
            return "Package version is required"
        
        return None
    
    def collect_metadata(self) -> Dict[str, Any]:
        """
        Collect package metadata from form fields.
        
        Returns:
            Dictionary containing package metadata
        """
        metadata = {
            "name": self.name_edit.text(),
            "version": self.version_edit.text(),
            "release": self.release_edit.text(),
            "summary": self.summary_edit.text(),
            "license": self.license_edit.text()
        }
        
        return metadata
    
    def start_conversion(self) -> None:
        """Start the conversion process."""
        # Validate inputs
        error = self.validate_inputs()
        if error:
            QMessageBox.warning(self, "Validation Error", error)
            return
        
        # Get parameters
        appimage_path = self.file_edit.text()
        output_dir = self.output_edit.text()
        metadata = self.collect_metadata()
        distro_profile = self.distro_combo.currentData()
        auto_deps = self.auto_deps_check.isChecked()
        
        # Update UI
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting conversion...")
        self.convert_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        
        # Emit signal
        self.conversion_started.emit()
        
        # Create and start the conversion thread
        self.conversion_thread = ConversionThread(
            controller=self.controller,
            appimage_path=appimage_path,
            output_dir=output_dir,
            metadata=metadata,
            distro_profile=distro_profile,
            auto_deps=auto_deps,
            is_directory=self.is_directory_mode
        )
        
        self.conversion_thread.progress_update.connect(self.update_progress)
        self.conversion_thread.conversion_finished.connect(self.on_conversion_finished)
        self.conversion_thread.start()
    
    def cancel_conversion(self) -> None:
        """Cancel the ongoing conversion process."""
        if self.conversion_thread and self.conversion_thread.isRunning():
            # This will only interrupt at certain points where the controller checks for cancellation
            self.conversion_thread.terminate()
            self.conversion_thread.wait()
            
            self.progress_bar.setValue(0)
            self.progress_label.setText("Conversion cancelled")
            self.convert_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
            
            logger.info("Conversion cancelled by user")
    
    @Slot(int, str)
    def update_progress(self, percent: int, message: str) -> None:
        """
        Update the progress bar and label.
        
        Args:
            percent: Completion percentage
            message: Progress message
        """
        self.progress_bar.setValue(percent)
        self.progress_label.setText(message)
    
    @Slot(bool, str, str)
    def on_conversion_finished(self, success: bool, rpm_path: str, message: str) -> None:
        """
        Handle completion of the conversion process.
        
        Args:
            success: Whether conversion was successful
            rpm_path: Path to the created RPM package
            message: Result message
        """
        # Update UI
        self.progress_label.setText(message)
        self.convert_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        
        if success:
            self.progress_bar.setValue(100)
            QMessageBox.information(
                self,
                "Conversion Complete",
                f"The AppImage was successfully converted to RPM.\nPackage: {rpm_path}"
            )
        else:
            self.progress_bar.setValue(0)
            QMessageBox.critical(
                self,
                "Conversion Failed",
                f"Failed to convert AppImage to RPM.\nError: {message}"
            )
        
        # Emit signal
        self.conversion_finished.emit(success, rpm_path, message) 