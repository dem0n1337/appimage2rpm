#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Distribution profile widget for AppImage2RPM.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QLineEdit, QFormLayout, QGroupBox, QScrollArea,
    QCheckBox, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizePolicy, QSpacerItem, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon

from appimage2rpm.core.controller import AppImage2RPMController
from appimage2rpm.core.distro_profile import DistroProfileManager


logger = logging.getLogger(__name__)


class DistroProfileWidget(QWidget):
    """
    Widget for managing distribution profiles.
    
    This widget allows users to view and edit distribution profiles
    that are used for RPM packaging.
    """
    
    profile_selected = Signal(str)
    
    def __init__(self, controller: Optional[AppImage2RPMController] = None) -> None:
        """
        Initialize the distribution profile widget.
        
        Args:
            controller: Optional AppImage2RPMController instance
        """
        super().__init__()
        
        self.controller = controller or AppImage2RPMController()
        self.current_profile: Optional[Dict[str, Any]] = None
        self.profiles: List[Dict[str, Any]] = []
        
        self.setup_ui()
        self.load_profiles()
    
    def setup_ui(self) -> None:
        """Set up the user interface for the distribution profile widget."""
        main_layout = QVBoxLayout(self)
        
        # Profile selection
        selection_group = QGroupBox("Distribution Profile")
        selection_layout = QHBoxLayout(selection_group)
        
        self.profile_label = QLabel("Select Distribution:")
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(200)
        self.profile_combo.currentIndexChanged.connect(self.on_profile_selected)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_profiles)
        
        selection_layout.addWidget(self.profile_label)
        selection_layout.addWidget(self.profile_combo)
        selection_layout.addWidget(self.refresh_button)
        selection_layout.addStretch()
        
        # Profile details
        details_group = QGroupBox("Profile Details")
        details_layout = QFormLayout(details_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)
        
        self.version_edit = QLineEdit()
        self.version_edit.setReadOnly(True)
        
        self.vendor_edit = QLineEdit()
        self.vendor_edit.setReadOnly(True)
        
        self.license_edit = QLineEdit()
        self.license_edit.setReadOnly(True)
        
        details_layout.addRow("Name:", self.name_edit)
        details_layout.addRow("Version:", self.version_edit)
        details_layout.addRow("Vendor:", self.vendor_edit)
        details_layout.addRow("License:", self.license_edit)
        
        # Dependencies table
        deps_group = QGroupBox("System Dependencies")
        deps_layout = QVBoxLayout(deps_group)
        
        self.deps_table = QTableWidget()
        self.deps_table.setColumnCount(2)
        self.deps_table.setHorizontalHeaderLabels(["Library Pattern", "Package Name"])
        self.deps_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        deps_layout.addWidget(self.deps_table)
        
        # Add everything to main layout
        main_layout.addWidget(selection_group)
        main_layout.addWidget(details_group)
        main_layout.addWidget(deps_group)
        main_layout.addStretch()
    
    def load_profiles(self) -> None:
        """Load all available distribution profiles."""
        self.profile_combo.clear()
        self.profiles = self.controller.get_available_profiles()
        
        if not self.profiles:
            self.profile_combo.addItem("No profiles available")
            self.profile_combo.setEnabled(False)
            return
        
        self.profile_combo.setEnabled(True)
        
        # Add profiles to combo box
        for profile in self.profiles:
            display_name = f"{profile.get('name', 'Unknown')} {profile.get('version', '')}"
            self.profile_combo.addItem(display_name.strip(), profile.get('id'))
        
        # Try to select current distro
        current_distro = self.controller.detect_current_distro()
        if current_distro:
            for i in range(self.profile_combo.count()):
                if self.profile_combo.itemData(i) == current_distro:
                    self.profile_combo.setCurrentIndex(i)
                    break
    
    @Slot(int)
    def on_profile_selected(self, index: int) -> None:
        """
        Handle selection of a profile from the combo box.
        
        Args:
            index: Index of the selected profile
        """
        if index < 0 or index >= len(self.profiles):
            self.current_profile = None
            self.clear_profile_details()
            return
        
        profile_id = self.profile_combo.itemData(index)
        self.current_profile = next((p for p in self.profiles if p.get('id') == profile_id), None)
        
        if self.current_profile:
            self.display_profile_details(self.current_profile)
            self.profile_selected.emit(profile_id)
    
    def clear_profile_details(self) -> None:
        """Clear all profile detail fields."""
        self.name_edit.setText("")
        self.version_edit.setText("")
        self.vendor_edit.setText("")
        self.license_edit.setText("")
        self.deps_table.setRowCount(0)
    
    def display_profile_details(self, profile: Dict[str, Any]) -> None:
        """
        Display the details of the selected profile.
        
        Args:
            profile: The profile data dictionary
        """
        # Basic info
        self.name_edit.setText(profile.get('name', ''))
        self.version_edit.setText(profile.get('version', ''))
        
        # RPM settings
        rpm_settings = profile.get('rpm_settings', {})
        self.vendor_edit.setText(rpm_settings.get('vendor', ''))
        self.license_edit.setText(rpm_settings.get('license', ''))
        
        # Dependencies
        self.deps_table.setRowCount(0)
        system_packages = profile.get('dependencies', {}).get('system_packages', {})
        
        self.deps_table.setRowCount(len(system_packages))
        for i, (lib, pkg) in enumerate(system_packages.items()):
            self.deps_table.setItem(i, 0, QTableWidgetItem(lib))
            self.deps_table.setItem(i, 1, QTableWidgetItem(pkg))
    
    def get_selected_profile_id(self) -> Optional[str]:
        """
        Get the ID of the currently selected profile.
        
        Returns:
            The selected profile ID or None if no profile is selected
        """
        index = self.profile_combo.currentIndex()
        if index >= 0:
            return self.profile_combo.itemData(index)
        return None 