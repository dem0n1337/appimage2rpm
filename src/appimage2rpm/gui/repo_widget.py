#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Repository manager widget for AppImage2RPM.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QFormLayout, QGroupBox, QFileDialog, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon

from appimage2rpm.core.controller import AppImage2RPMController
from appimage2rpm.core.repo_manager import RepoManager


logger = logging.getLogger(__name__)


class RepoManagerWidget(QWidget):
    """
    Widget for managing RPM repositories.
    
    This widget allows users to create, update, and manage
    RPM repositories for the converted packages.
    """
    
    def __init__(self, controller: Optional[AppImage2RPMController] = None) -> None:
        """
        Initialize the repository manager widget.
        
        Args:
            controller: Optional AppImage2RPMController instance
        """
        super().__init__()
        
        self.controller = controller or AppImage2RPMController()
        self.repo_manager = RepoManager()
        self.current_repo_path: Optional[Path] = None
        
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Set up the user interface for the repository manager widget."""
        main_layout = QVBoxLayout(self)
        
        # Repository configuration section
        repo_config_group = QGroupBox("Repository Configuration")
        config_layout = QFormLayout(repo_config_group)
        
        self.repo_path_edit = QLineEdit()
        self.repo_path_button = QPushButton("Browse...")
        self.repo_path_button.clicked.connect(self.browse_repo_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.repo_path_edit)
        path_layout.addWidget(self.repo_path_button)
        
        self.repo_name_edit = QLineEdit()
        self.repo_desc_edit = QLineEdit()
        
        config_layout.addRow("Repository Path:", path_layout)
        config_layout.addRow("Repository Name:", self.repo_name_edit)
        config_layout.addRow("Description:", self.repo_desc_edit)
        
        # Action buttons
        action_layout = QHBoxLayout()
        
        self.create_repo_button = QPushButton("Create Repository")
        self.create_repo_button.clicked.connect(self.create_repository)
        
        self.add_package_button = QPushButton("Add Package...")
        self.add_package_button.clicked.connect(self.add_package)
        self.add_package_button.setEnabled(False)
        
        self.update_repo_button = QPushButton("Update Metadata")
        self.update_repo_button.clicked.connect(self.update_repository)
        self.update_repo_button.setEnabled(False)
        
        action_layout.addWidget(self.create_repo_button)
        action_layout.addWidget(self.add_package_button)
        action_layout.addWidget(self.update_repo_button)
        
        # Packages list
        packages_group = QGroupBox("Repository Packages")
        packages_layout = QVBoxLayout(packages_group)
        
        self.packages_table = QTableWidget()
        self.packages_table.setColumnCount(3)
        self.packages_table.setHorizontalHeaderLabels(["Name", "Version", "Type"])
        self.packages_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.packages_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_packages)
        
        packages_layout.addWidget(self.packages_table)
        packages_layout.addWidget(refresh_button)
        
        # Add all sections to main layout
        main_layout.addWidget(repo_config_group)
        main_layout.addLayout(action_layout)
        main_layout.addWidget(packages_group)
    
    def browse_repo_path(self) -> None:
        """Browse for repository directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Repository Directory",
            str(Path.home())
        )
        
        if directory:
            self.repo_path_edit.setText(directory)
    
    def create_repository(self) -> None:
        """Create a new RPM repository."""
        repo_path = self.repo_path_edit.text().strip()
        repo_name = self.repo_name_edit.text().strip()
        repo_desc = self.repo_desc_edit.text().strip()
        
        if not repo_path:
            QMessageBox.warning(self, "Error", "Repository path is required")
            return
        
        if not repo_name:
            QMessageBox.warning(self, "Error", "Repository name is required")
            return
        
        try:
            # Create the repository
            repo_dir = self.repo_manager.create_repository(
                repo_path,
                repo_name,
                repo_desc or repo_name
            )
            
            self.current_repo_path = repo_dir
            self.add_package_button.setEnabled(True)
            self.update_repo_button.setEnabled(True)
            
            # Refresh the packages list
            self.refresh_packages()
            
            QMessageBox.information(
                self,
                "Repository Created",
                f"Repository successfully created at {repo_dir}"
            )
            
            logger.info(f"Created repository at {repo_dir}")
            
        except Exception as e:
            logger.error(f"Error creating repository: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error creating repository: {str(e)}")
    
    def add_package(self) -> None:
        """Add a package to the repository."""
        if not self.current_repo_path:
            QMessageBox.warning(self, "Error", "No repository selected")
            return
        
        # Open file dialog to select RPM package
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select RPM Package",
            str(Path.home()),
            "RPM Packages (*.rpm)"
        )
        
        if not file_path:
            return
        
        try:
            # Add the package to the repository
            success = self.repo_manager.add_package(
                self.current_repo_path,
                file_path
            )
            
            if success:
                # Refresh the packages list
                self.refresh_packages()
                
                QMessageBox.information(
                    self,
                    "Package Added",
                    f"Package successfully added to repository"
                )
                
                logger.info(f"Added package {file_path} to repository")
            else:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Failed to add package to repository"
                )
            
        except Exception as e:
            logger.error(f"Error adding package: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error adding package: {str(e)}")
    
    def update_repository(self) -> None:
        """Update the repository metadata."""
        if not self.current_repo_path:
            QMessageBox.warning(self, "Error", "No repository selected")
            return
        
        try:
            # Update repository metadata
            success = self.repo_manager.update_repository_metadata(
                self.current_repo_path
            )
            
            if success:
                QMessageBox.information(
                    self,
                    "Repository Updated",
                    "Repository metadata successfully updated"
                )
                
                logger.info(f"Updated repository metadata at {self.current_repo_path}")
            else:
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Failed to update repository metadata"
                )
            
        except Exception as e:
            logger.error(f"Error updating repository: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error updating repository: {str(e)}")
    
    def refresh_packages(self) -> None:
        """Refresh the list of packages in the repository."""
        self.packages_table.setRowCount(0)
        
        if not self.current_repo_path:
            return
        
        # Look for RPM packages in RPMS and SRPMS directories
        rpms_dir = self.current_repo_path / "RPMS"
        srpms_dir = self.current_repo_path / "SRPMS"
        
        packages = []
        
        # Add binary RPMs
        if rpms_dir.exists():
            for rpm_file in rpms_dir.glob("*.rpm"):
                packages.append((rpm_file.name, "Binary"))
        
        # Add source RPMs
        if srpms_dir.exists():
            for rpm_file in srpms_dir.glob("*.rpm"):
                packages.append((rpm_file.name, "Source"))
        
        # Fill the table
        self.packages_table.setRowCount(len(packages))
        for i, (name, type_) in enumerate(packages):
            # Extract name and version (simplified)
            parts = name.replace(".rpm", "").split("-")
            if len(parts) >= 2:
                pkg_name = "-".join(parts[:-2])
                pkg_version = "-".join(parts[-2:])
            else:
                pkg_name = name
                pkg_version = ""
            
            self.packages_table.setItem(i, 0, QTableWidgetItem(pkg_name))
            self.packages_table.setItem(i, 1, QTableWidgetItem(pkg_version))
            self.packages_table.setItem(i, 2, QTableWidgetItem(type_))
        
        # Sort by name
        self.packages_table.sortItems(0) 