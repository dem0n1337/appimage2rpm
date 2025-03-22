#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
About dialog for AppImage2RPM application.
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextBrowser, QTabWidget
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QFont, QIcon

import appimage2rpm


class AboutDialog(QDialog):
    """
    About dialog showing information about the application.
    
    This dialog provides information about the application, its version,
    license, and credits.
    """
    
    def __init__(self, parent=None) -> None:
        """
        Initialize the about dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("About AppImage2RPM")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Set up the user interface for the about dialog."""
        layout = QVBoxLayout(self)
        
        # Header with app name and version
        header_layout = QHBoxLayout()
        
        # Logo
        logo_label = QLabel()
        logo_pixmap = QPixmap()  # Replace with actual logo if available
        if logo_pixmap:
            logo_label.setPixmap(logo_pixmap.scaled(QSize(64, 64), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback to text if no logo is available
            logo_label.setText("🔄")
            logo_label.setFont(QFont("Arial", 32))
            logo_label.setAlignment(Qt.AlignCenter)
            logo_label.setMinimumWidth(64)
        
        # App info
        version = getattr(appimage2rpm, "__version__", "1.0.0")
        info_label = QLabel(f"<h2>AppImage2RPM</h2><p>Version {version}</p>")
        info_label.setTextFormat(Qt.RichText)
        
        header_layout.addWidget(logo_label)
        header_layout.addWidget(info_label)
        header_layout.addStretch()
        
        # Tabs for different information
        tabs = QTabWidget()
        
        # About tab
        about_widget = QTextBrowser()
        about_widget.setOpenExternalLinks(True)
        about_widget.setHtml("""
        <h3>AppImage2RPM Converter</h3>
        <p>A tool to convert AppImage packages to RPM format for better integration with RPM-based Linux distributions.</p>
        <p>AppImage2RPM extracts AppImage packages, analyzes dependencies, and creates RPM packages that can be installed using standard package management tools.</p>
        <p>Visit the project website: <a href="https://github.com/yourusername/appimage2rpm">GitHub Repository</a></p>
        """)
        
        # License tab
        license_widget = QTextBrowser()
        license_widget.setPlainText("""
MIT License

Copyright (c) 2023 AppImage2RPM Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
        """)
        
        # Credits tab
        credits_widget = QTextBrowser()
        credits_widget.setHtml("""
        <h3>Credits</h3>
        <p>AppImage2RPM uses the following open source technologies:</p>
        <ul>
            <li>Python</li>
            <li>Qt / PySide6</li>
            <li>RPM build tools</li>
            <li>AppImage runtime</li>
        </ul>
        <p>Special thanks to all contributors and the open source community.</p>
        """)
        
        tabs.addTab(about_widget, "About")
        tabs.addTab(license_widget, "License")
        tabs.addTab(credits_widget, "Credits")
        
        # Close button
        button_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        # Add all widgets to main layout
        layout.addLayout(header_layout)
        layout.addWidget(tabs)
        layout.addLayout(button_layout) 